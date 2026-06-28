import asyncio
import logging
import os
import shlex
import signal
import subprocess
from pathlib import Path

from app.core.config import get_settings
from app.models.instance import Instance
from app.models.template import Template

import collections

logger = logging.getLogger(__name__)


class ConsoleBuffer:
    def __init__(self, instance_id: str, socket_path: str):
        self.instance_id = instance_id
        self.socket_path = socket_path
        self.lines = collections.deque(maxlen=1000)
        self.current_line = bytearray()
        self.websockets = set()
        self.writer = None
        self.task = None

    def append_bytes(self, data: bytes):
        # 广播给当前连接的所有 WebSocket 客户端
        for ws in list(self.websockets):
            try:
                asyncio.create_task(ws.send_bytes(data))
            except Exception:
                self.websockets.discard(ws)

        # 记录 1000 行历史记录
        for b in data:
            if b == 10:  # \n
                self.current_line.append(b)
                self.lines.append(bytes(self.current_line))
                self.current_line = bytearray()
            else:
                self.current_line.append(b)
                if len(self.current_line) > 4096:
                    self.lines.append(bytes(self.current_line))
                    self.current_line = bytearray()

    async def start_reading(self):
        while True:
            if not Path(self.socket_path).exists():
                await asyncio.sleep(0.5)
                continue
            try:
                reader, writer = await asyncio.open_unix_connection(self.socket_path)
                self.writer = writer
                logger.info(f"串口背景监听连接成功: {self.socket_path}")
                while True:
                    data = await reader.read(4096)
                    if not data:
                        break
                    self.append_bytes(data)
            except Exception as e:
                logger.debug(f"串口背景监听读取异常: {e}")
                await asyncio.sleep(1.0)
            finally:
                self.writer = None

    def write_bytes(self, data: bytes):
        if self.writer:
            try:
                self.writer.write(data)
                asyncio.create_task(self.writer.drain())
            except Exception as e:
                logger.debug(f"串口写入数据异常: {e}")


console_managers: dict[str, ConsoleBuffer] = {}


def ensure_console_reader(instance_id: str) -> ConsoleBuffer:
    cb = console_managers.get(instance_id)
    if not cb:
        serial_path = serial_socket_path(instance_id)
        cb = ConsoleBuffer(instance_id, serial_path)
        cb.task = asyncio.create_task(cb.start_reading())
        console_managers[instance_id] = cb
    return cb


def tap_name_for(instance_id: str) -> str:
    short = instance_id.removeprefix("inst_").replace("-", "")[:8]
    return f"tap_{short}"


def serial_socket_path(instance_id: str) -> str:
    settings = get_settings()
    return str(Path(settings.QEMU_SERIAL_DIR) / f"qemu_serial_{instance_id}.sock")


def build_cmd(instance: Instance, template: Template) -> list[str]:
    settings = get_settings()
    drive = instance.drive_path or template.drive_path
    serial = instance.serial_socket or serial_socket_path(instance.id)
    tap = instance.tap_name or tap_name_for(instance.id)

    cmd = [
        template.qemu_binary,
        "-M",
        template.machine,
        "-cpu",
        template.cpu,
        "-m",
        f"{template.ram_size}M",
        "-display",
        "none",
        "-kernel",
        template.kernel_path,
        "-append",
        template.kernel_append,
        "-drive",
        f"if=none,file={drive},format=raw,id=hd",
        "-device",
        "virtio-blk-device,drive=hd",
        "-netdev",
        f"tap,id=net0,ifname={tap},script=no,downscript=no",
        "-device",
        "virtio-net-pci,netdev=net0",
        "-serial",
        f"unix:{serial},server,nowait",
    ]
    if template.extra_args:
        cmd.extend(shlex.split(template.extra_args))
    return cmd


async def run_cmd(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    result = subprocess.CompletedProcess(
        args=args,
        returncode=proc.returncode or 0,
        stdout=stdout.decode(),
        stderr=stderr.decode(),
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"Command failed: {' '.join(args)}")
    return result


async def setup_tap(instance: Instance) -> str:
    from app.services.network_setup import add_tap_to_bridge

    settings = get_settings()
    tap = tap_name_for(instance.id)
    bridge = instance.bridge_name or settings.FSEMS_BRIDGE
    await add_tap_to_bridge(tap, bridge, settings.fsems_user)
    return tap


async def teardown_tap(tap_name: str | None, bridge: str | None = None) -> None:
    if not tap_name:
        return
    from app.services.network_setup import remove_tap

    settings = get_settings()
    await remove_tap(tap_name, bridge or settings.FSEMS_BRIDGE)


import time

async def wait_boot(host: str, port: int, timeout_sec: int) -> bool:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=3)
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, asyncio.TimeoutError):
            await asyncio.sleep(2)
    return False


async def start_instance(instance: Instance, template: Template) -> int:
    settings = get_settings()
    tap = await setup_tap(instance)
    instance.tap_name = tap
    instance.serial_socket = serial_socket_path(instance.id)
    instance.guest_ssh_host = instance.guest_ssh_host or template.guest_ssh_host

    old_socket = Path(instance.serial_socket)
    if old_socket.exists():
        old_socket.unlink()

    cmd = build_cmd(instance, template)
    logger.info("Starting QEMU: %s", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    
    # 立即拉起串口背景监听，确保不会丢失开机引导日志
    ensure_console_reader(instance.id)
    
    return proc.pid


def is_pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # 权限不够也说明进程存在
        return True


async def stop_process(pid: int | None) -> None:
    if not pid:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    for _ in range(10):
        await asyncio.sleep(1)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


async def cleanup_instance_resources(instance: Instance) -> None:
    await stop_process(instance.pid)
    await teardown_tap(instance.tap_name, instance.bridge_name)
    if instance.serial_socket and Path(instance.serial_socket).exists():
        Path(instance.serial_socket).unlink(missing_ok=True)

    # 停止并销毁当前实例关联的串口背景监听器
    cb = console_managers.pop(instance.id, None)
    if cb:
        if cb.task:
            cb.task.cancel()
        if cb.writer:
            try:
                cb.writer.close()
            except Exception:
                pass
