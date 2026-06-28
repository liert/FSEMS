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
| 网络 | **TAP + `br_fsems`**，不用 `-netdev user` hostfwd |
| SSH/SCP 目标 | **`192.168.1.1:22`**（模板 `guest_ssh_host`），不是 `127.0.0.1:22222` |
| Phase 1 | **同时仅 1 个 RUNNING 实例** |

---

## 技术栈

Vue 3 + TS + Element Plus + Xterm.js | FastAPI + SQLAlchemy + aiosqlite + Celery + Redis | QEMU + TAP

---

## 本地开发

```bash
sudo ./scripts/install_host_deps.sh
sudo ./scripts/setup_network.sh
cp .env.example .env
sudo mkdir -p /var/fsems/{data,workspace,images,kernels,mnt}
sudo chown -R "$USER:$USER" /var/fsems
# 复制固件到 /var/fsems/kernels 与 /var/fsems/images（见开发文档 §4.4）
```

Backend 与 Celery **同一用户**、**同一 `.env`**。

---

## QEMU 要点（`qemu_manager.py`）

1. `setup_tap`: 创建 `tap_{id[:8]}`，加入 `br_fsems`
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

## Phase 1 编码顺序

严格按开发文档 **§13** 步骤 1→10 实现；不要跳步同时写 Celery/SCP（属 Phase 2）。

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

**Phase 1 已实现**（backend + frontend 骨架）。后续按 §13 Phase 2 接入 Celery/SCP/访客机 VFS。
