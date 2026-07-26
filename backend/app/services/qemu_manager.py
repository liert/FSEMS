import asyncio
import collections
import json
import logging
import os
import shlex
import shutil
import signal
import subprocess
import time
from pathlib import Path

from app.core.config import get_settings
from app.models.instance import Instance
from app.models.template import Template

logger = logging.getLogger(__name__)


class ConsoleBuffer:
    def __init__(self, instance_id: str, socket_path: str, log_path: str):
        self.instance_id = instance_id
        self.socket_path = socket_path
        self.log_path = log_path
        self.lines = collections.deque(maxlen=1000)
        self.current_line = bytearray()
        self.websockets = set()
        self.writer = None
        self.task = None
        self.cols = 80
        self.rows = 24

    def append_bytes(self, data: bytes):
        try:
            log_file = Path(self.log_path)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with log_file.open("ab") as f:
                f.write(data)
        except OSError as exc:
            logger.debug("写入实例串口日志失败 %s: %s", self.log_path, exc)

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

    def write_resize(self, cols: int, rows: int) -> None:
        """Record terminal dimensions for the web client only.

        Do not inject ``stty`` into the guest serial line — OpenWrt/BusyBox
        images often lack ``stty``, and QEMU serial is not a resize-aware TTY.
        """
        self.cols = max(1, min(int(cols), 500))
        self.rows = max(1, min(int(rows), 500))


console_managers: dict[str, ConsoleBuffer] = {}
processes: dict[str, subprocess.Popen] = {}
process_monitors: dict[str, asyncio.Task] = {}


def instance_workspace(instance_id: str) -> Path:
    return (get_settings().workspace_path / instance_id).resolve()


def qemu_command_path(instance_id: str) -> Path:
    return instance_workspace(instance_id) / "qemu-command.json"


def qemu_stderr_path(instance_id: str) -> Path:
    return instance_workspace(instance_id) / "qemu-stderr.log"


def serial_log_path(instance_id: str) -> Path:
    return instance_workspace(instance_id) / "serial.log"


def qemu_exit_path(instance_id: str) -> Path:
    return instance_workspace(instance_id) / "qemu-exit.json"


def ensure_console_reader(instance_id: str) -> ConsoleBuffer:
    cb = console_managers.get(instance_id)
    if not cb:
        serial_path = serial_socket_path(instance_id)
        cb = ConsoleBuffer(instance_id, serial_path, str(serial_log_path(instance_id)))
        cb.task = asyncio.create_task(cb.start_reading())
        console_managers[instance_id] = cb
    return cb


def tap_name_for(instance_id: str) -> str:
    short = instance_id.removeprefix("inst_").replace("-", "")[:8]
    return f"tap_{short}"


def serial_socket_path(instance_id: str) -> str:
    settings = get_settings()
    return str(Path(settings.QEMU_SERIAL_DIR) / f"qemu_serial_{instance_id}.sock")


def block_device_arg(machine: str) -> str | None:
    """返回需要显式添加的块设备；Malta 使用内建 PIIX IDE 控制器。"""
    if machine == "malta":
        return None
    if machine == "virt":
        return "virtio-blk-device,drive=hd"
    return "virtio-blk-pci,drive=hd"


def net_device_arg(machine: str) -> str:
    if machine == "malta":
        return "pcnet,netdev=net0"
    return "virtio-net-pci,netdev=net0"


def effective_kernel_append(template: Template) -> str:
    """修正常见的跨架构模板参数，同时保留用户的其他内核参数。"""
    append = template.kernel_append or ""
    if template.machine == "malta":
        append = append.replace("root=/dev/vda", "root=/dev/sda")
        append = append.replace("console=ttyAMA0", "console=ttyS0,38400n8")
        if "console=" not in append:
            append = f"{append} console=ttyS0,38400n8"
        if "rootwait" not in append.split():
            append = f"{append} rootwait"
    return " ".join(append.split())


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
        effective_kernel_append(template),
    ]
    block_device = block_device_arg(template.machine)
    if block_device is None:
        cmd.extend(["-drive", f"file={drive},format=raw,if=ide,index=0,media=disk"])
    else:
        cmd.extend([
            "-drive",
            f"if=none,file={drive},format=raw,id=hd",
            "-device",
            block_device,
        ])
    cmd.extend([
        "-netdev",
        f"tap,id=net0,ifname={tap},script=no,downscript=no",
        "-device",
        net_device_arg(template.machine),
        "-serial",
        f"unix:{serial},server,nowait",
    ])
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


def tail_text(path: Path, max_bytes: int = 64 * 1024) -> str:
    if not path.is_file():
        return ""
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - max_bytes))
        return f.read().decode(errors="replace")


async def _monitor_process(instance_id: str, proc: subprocess.Popen) -> None:
    returncode = await asyncio.to_thread(proc.wait)
    exit_data = {"pid": proc.pid, "returncode": returncode, "exited_at": time.time()}
    path = qemu_exit_path(instance_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(exit_data, ensure_ascii=False, indent=2), encoding="utf-8")
    processes.pop(instance_id, None)
    process_monitors.pop(instance_id, None)
    logger.warning("QEMU exited instance=%s pid=%s returncode=%s", instance_id, proc.pid, returncode)


async def start_instance(instance: Instance, template: Template) -> int:
    tap = await setup_tap(instance)
    instance.tap_name = tap
    instance.serial_socket = serial_socket_path(instance.id)
    instance.guest_ssh_host = instance.guest_ssh_host or template.guest_ssh_host

    old_socket = Path(instance.serial_socket)
    if old_socket.exists():
        old_socket.unlink()

    workspace = instance_workspace(instance.id)
    workspace.mkdir(parents=True, exist_ok=True)
    stderr_path = qemu_stderr_path(instance.id)
    serial_path = serial_log_path(instance.id)
    exit_path = qemu_exit_path(instance.id)
    stderr_path.write_bytes(b"")
    serial_path.write_bytes(b"")
    exit_path.unlink(missing_ok=True)

    cmd = build_cmd(instance, template)
    qemu_command_path(instance.id).write_text(
        json.dumps({"argv": cmd, "shell": shlex.join(cmd)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Starting QEMU: %s", shlex.join(cmd))

    try:
        with stderr_path.open("ab", buffering=0) as stderr_file:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
                start_new_session=True,
            )
    except Exception:
        await teardown_tap(instance.tap_name, instance.bridge_name)
        raise

    processes[instance.id] = proc
    monitor = asyncio.create_task(_monitor_process(instance.id, proc))
    process_monitors[instance.id] = monitor

    # 立即拉起串口背景监听，确保不会丢失开机引导日志。
    ensure_console_reader(instance.id)

    # 在报告启动成功前捕获参数、设备模型和权限导致的立即退出。
    await asyncio.sleep(1.0)
    returncode = proc.poll()
    if returncode is not None:
        try:
            await monitor
        except asyncio.CancelledError:
            pass
        await teardown_tap(instance.tap_name, instance.bridge_name)
        stderr_tail = tail_text(stderr_path).strip()
        raise RuntimeError(
            f"QEMU exited during launch (exit {returncode})"
            + (f": {stderr_tail}" if stderr_tail else "")
        )

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


def _file_info(path: str | Path | None) -> dict:
    p = Path(path) if path else None
    exists = bool(p and p.is_file())
    info = {"path": str(p) if p else None, "exists": exists, "size": p.stat().st_size if exists else None}
    if exists:
        try:
            proc = subprocess.run(["file", "-b", str(p)], capture_output=True, text=True, timeout=5)
            info["type"] = proc.stdout.strip() if proc.returncode == 0 else proc.stderr.strip()
        except Exception as exc:
            info["type"] = f"unavailable: {exc}"
    else:
        info["type"] = None
    return info


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


async def instance_diagnostics(instance: Instance, template: Template, serial_lines: int = 200) -> dict:
    command_data = _read_json(qemu_command_path(instance.id)) or {}
    exit_data = _read_json(qemu_exit_path(instance.id))
    proc = processes.get(instance.id)
    live_returncode = proc.poll() if proc else None
    if live_returncode is not None and exit_data is None:
        exit_data = {"pid": proc.pid, "returncode": live_returncode}

    tap = instance.tap_name or tap_name_for(instance.id)
    tap_exists = False
    bridge_attached = False
    try:
        tap_check = await run_cmd(["ip", "link", "show", tap], check=False)
        tap_exists = tap_check.returncode == 0
        if tap_exists:
            bridge_check = await run_cmd(["bridge", "link", "show", "dev", tap], check=False)
            bridge_attached = (instance.bridge_name or get_settings().FSEMS_BRIDGE) in bridge_check.stdout
    except Exception:
        pass

    ssh_reachable = False
    host = instance.guest_ssh_host or template.guest_ssh_host
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, template.guest_ssh_port), timeout=0.75
        )
        writer.close()
        await writer.wait_closed()
        ssh_reachable = True
    except (OSError, asyncio.TimeoutError):
        pass

    serial_tail = tail_text(serial_log_path(instance.id))
    if serial_lines > 0:
        serial_tail = "".join(serial_tail.splitlines(keepends=True)[-min(serial_lines, 2000):])

    return {
        "id": instance.id,
        "status": instance.status,
        "pid": instance.pid,
        "pid_alive": is_pid_alive(instance.pid),
        "qemu_binary": {
            "configured": template.qemu_binary,
            "resolved": shutil.which(template.qemu_binary),
        },
        "qemu_command": command_data.get("argv"),
        "qemu_command_shell": command_data.get("shell"),
        "qemu_exit": exit_data,
        "qemu_stderr_tail": tail_text(qemu_stderr_path(instance.id)),
        "serial_tail": serial_tail,
        "serial_socket": instance.serial_socket or serial_socket_path(instance.id),
        "serial_socket_exists": Path(instance.serial_socket or serial_socket_path(instance.id)).exists(),
        "kernel": _file_info(template.kernel_path),
        "drive": {
            **_file_info(instance.drive_path or template.drive_path),
            "root_device": "/dev/sda" if template.machine == "malta" else "/dev/vda",
            "writable": bool(instance.drive_path or template.drive_path)
            and os.access(instance.drive_path or template.drive_path, os.W_OK),
        },
        "template": {
            "id": template.id,
            "name": template.name,
            "arch": template.arch,
            "machine": template.machine,
            "cpu": template.cpu,
            "configured_append": template.kernel_append,
            "effective_append": effective_kernel_append(template),
            "block_device": block_device_arg(template.machine) or "ide",
            "network_device": net_device_arg(template.machine),
        },
        "network": {
            "tap": tap,
            "tap_exists": tap_exists,
            "bridge": instance.bridge_name or get_settings().FSEMS_BRIDGE,
            "bridge_attached": bridge_attached,
            "guest_ip": host,
            "guest_ssh_port": template.guest_ssh_port,
            "ssh_reachable": ssh_reachable,
        },
        "paths": {
            "workspace": str(instance_workspace(instance.id)),
            "command": str(qemu_command_path(instance.id)),
            "stderr": str(qemu_stderr_path(instance.id)),
            "serial_log": str(serial_log_path(instance.id)),
            "exit": str(qemu_exit_path(instance.id)),
        },
        "error_msg": instance.error_msg,
    }


async def stop_process(pid: int | None, *, allow_sigkill: bool = True) -> bool:
    """发送 SIGTERM 等待进程退出。返回是否已成功停止。"""
    if not pid:
        return True
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    grace_sec = 30 if not allow_sigkill else 10
    for _ in range(grace_sec):
        await asyncio.sleep(1)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
    if not allow_sigkill:
        logger.warning("QEMU pid=%s 在 %ss 内未优雅退出", pid, grace_sec)
        return False
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    await asyncio.sleep(0.5)
    try:
        os.kill(pid, 0)
        return False
    except ProcessLookupError:
        return True


async def cleanup_instance_resources(instance: Instance, *, allow_sigkill: bool = True) -> None:
    if instance.pid and not await stop_process(instance.pid, allow_sigkill=allow_sigkill):
        raise RuntimeError("QEMU 未能在规定时间内优雅停止")
    processes.pop(instance.id, None)
    monitor = process_monitors.pop(instance.id, None)
    if monitor and not monitor.done():
        monitor.cancel()
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
