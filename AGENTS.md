# FSEMS — AI 编码代理指南

面向 Cursor 等 AI 代理。**编码前必读**。详细规格见 [`docs/FSEMS_development_document.md`](docs/FSEMS_development_document.md)。

---

## 项目简介

**FSEMS**：Web 管理 QEMU 上的 OpenWrt/IoT 固件——实例生命周期、串口控制台、双栏文件管理、SCP 传输。

QEMU 启动方式参考用户脚本：`/home/kali/openwrt/armv8/start.sh`（TAP + 网桥 + `qemu-system-aarch64 -M virt`）。

---

## 硬性约束

| 约束 | 说明 |
| :--- | :--- |
| 不用 Docker | 宿主机原生进程 |
| SQLite3 | WAL，`DATABASE_URL` 见 `.env.example` |
| 不用 libvirt | 仅 `subprocess` 管理 QEMU |
| 网络 | **TAP + 网桥**（默认 `br_fsems`），不用 `-netdev user` hostfwd |
| SSH/SCP 目标 | 实例 `guest_ssh_host:22`（创建时分配，非 `127.0.0.1:22222`） |
| 多实例 | 同网桥模式按 `192.168.1.X` 分配 IP；独立网桥模式使用 `br_fs_X` + `192.168.X.0/24` |

---

## 技术栈

Vue 3 + TS + Element Plus + Xterm.js | FastAPI + SQLAlchemy + aiosqlite + Celery + Redis | QEMU + TAP

---

## 本地开发

```bash
# 依赖安装（请参考 README.md「快速开始」使用 apt 独立安装各依赖与 Redis）
sudo ./scripts/setup_network.sh
cp .env.example .env
sudo mkdir -p /var/fsems/{data,workspace,images,kernels,mnt}
sudo chown -R "$USER:$USER" /var/fsems
# 复制固件到 /var/fsems/kernels 与 /var/fsems/rootfs（见开发文档 §4.4）
```

Backend 与 Celery **同一用户**、**同一 `.env`**。`uvicorn` 启动时会自动尝试拉起 Redis 与 Celery worker（见 `app/main.py` lifespan）。

```bash
./scripts/dev_start.sh   # 或分别启动 backend + frontend
```

TAP/网桥操作需 **root 或免密 sudo**；开发环境建议 `sudo` 启动后端。

---

## QEMU 要点（`qemu_manager.py`）

1. `setup_tap`: 创建 `tap_{id[:8]}`，加入实例所属网桥
2. 启动命令见开发文档 **§5.2.2**（基于用户 start.sh，串口改 Unix Socket）
3. `wait_boot`: TCP 探活 `guest_ssh_host:22`，超时 `BOOT_TIMEOUT_SEC`
4. `stop`: SIGTERM → 清理 TAP + serial socket

---

## API 约定

- 前缀 `/api/v1/`，统一信封 `{ success, data, error_code, message }`
- 认证：`.env` 单用户 `FSEMS_ADMIN_USER` / `FSEMS_ADMIN_PASSWORD` → JWT
- WebSocket 串口：§5.4，Binary 帧 + `?token=`

主要端点见开发文档 §6。

---

## 禁止

- Docker / PostgreSQL / libvirt
- `127.0.0.1` 端口转发式 SSH（与当前 TAP 设计冲突）
- 未经路径校验暴露宿主机任意目录
- 未请求时不要 git commit

---

## 实现阶段

| 阶段 | 状态 | 说明 |
| :--- | :--- | :--- |
| Phase 1 | 已完成 | 认证、模板列表、实例 CRUD/生命周期、串口 WS、宿主机 VFS、日志 |
| Phase 2 | 已完成 | Celery SCP、`/fs/guest`、`/fs/transfer`、双栏 `FileManager.vue`、任务进度 |
| Phase 3 | 已完成 | 离线 VFS、模板 CRUD/UI、串口 resize、磁盘快照、多架构 seed |

## 文档索引

| 章节 | 内容 |
| :--- | :--- |
| §5.2 | QEMU 命令行（基于 `start.sh`） |
| §5.4 | WebSocket 串口协议 |
| §6 | API 与认证 |
| §9 | SQLite 表结构 |
| §10 | 前端路由与 Vite 代理 |
| §11 | Python/Node 依赖版本 |
| §12 | 文档就绪检查清单 |
| §13 | Phase 1 编码顺序 |

## 文档状态

**Phase 1–3 功能已实现。** 后续可按需扩展 qcow2 快照、传输字节级进度、多用户认证等。
