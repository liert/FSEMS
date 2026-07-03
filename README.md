# FSEMS

固件模拟环境管理系统（Firmware Simulation Environment Management System）。

基于 Web 统一管理 QEMU 上的 OpenWrt 固件实例：生命周期、控制台、宿主机/访客机双栏文件浏览与 SCP 传输。

## 文档

| 文件 | 说明 |
| :--- | :--- |
| [AGENTS.md](AGENTS.md) | AI 编码代理指南 |
| [docs/FSEMS_development_document.md](docs/FSEMS_development_document.md) | 完整开发规格 |

## 架构要点

- 全宿主机原生运行（无 Docker）
- SQLite3 + Redis + Celery
- QEMU：TAP + 网桥（参考 `/home/kali/openwrt/armv8/start.sh`）
- OpenWrt ARMv8 seed 模板；支持多实例（同网段 IP 分配或独立网桥）

## 快速开始

```bash
sudo ./scripts/install_host_deps.sh
sudo ./scripts/setup_network.sh
cp .env.example .env
# 编辑 .env：至少设置 FSEMS_GUEST_SSH_PASSWORD
sudo mkdir -p /var/fsems/{data,workspace,kernels,rootfs,mnt}
sudo chown -R "$USER:$USER" /var/fsems
```

固件文件放入 `data/kernels/` 与 `data/rootfs/`（生产环境 `/var/fsems/kernels/`、`/var/fsems/rootfs/`）。支持 ARMv8、MIPS、MIPSEL、x86_64，文件名见开发文档 §4.4。

```bash
# 开发环境（TAP/guestmount 建议 root 启动后端）
sudo ./scripts/dev_start.sh
# 或手动：sudo backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --app-dir backend
```

开发环境也可使用仓库内 `./data/` 路径（见 `.env.example`）。

## 功能概览

| 模块 | 说明 |
| :--- | :--- |
| 实例管理 | 创建/启动/停止/重启/删除；同网段或独立网桥；过渡状态自动刷新 |
| 实例管理中心 | `/instances/:id/manage` — 基本信息、控制台、双栏文件管理 |
| 控制台 | WebSocket + Xterm（QEMU 串口） |
| 文件传输 | Celery 异步 SCP；顶栏「后台任务」统一进度 |
| 宿主机上传 | 文件管理器 Host 面板「上传」按钮 |
| 访客机文件操作 | 在线模式：新建文件夹、重命名、删除（SSH） |
| 离线 VFS | 实例 STOPPED 时 debugfs / guestmount 只读浏览 rootfs.img |
| 磁盘快照 | 异步创建/恢复/删除（qcow2 压缩；实例 STOPPED） |
| 磁盘扩容 | `qemu-img resize` + `resize2fs` |
| 模板管理 | 多架构 CRUD |
| 系统日志 | FastAPI / Celery / 前端客户端错误上报 |
| UI | 浅/深色主题、侧栏折叠 |

## 实现阶段

- **Phase 1–3**：已实现（见 [AGENTS.md](AGENTS.md)）
- **CI**：GitHub Actions 运行 `pytest` 与 `npm run build`

## 启动方式

```bash
# 一键开发（推荐 root/sudo 以支持 TAP 与离线 VFS）
sudo ./scripts/dev_start.sh

# 或手动
cd backend && source .venv/bin/activate
sudo uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --app-dir .
# 另开终端
cd frontend && npm run dev
```

后端 lifespan 会自动尝试启动 Redis 与 Celery worker；TAP/网桥/guestmount 操作建议以 **root 或免密 sudo** 运行后端。

## 生产部署

```bash
sudo ./scripts/install_host_deps.sh
sudo ./scripts/setup_network.sh
sudo ./scripts/install_production.sh
# 编辑 /etc/fsems/fsems.env 后：
sudo systemctl enable --now fsems-api fsems-celery
```

使用 Nginx 反代 `127.0.0.1:8000` 的 `/api/v1`，并将 `frontend/dist` 作为静态站点；WebSocket 需配置 `/api/v1/instances/` 的 upgrade 头。

默认登录：`admin` / `admin`（见 `.env`，生产环境务必修改）。
