# FSEMS

固件模拟环境管理系统（Firmware Simulation Environment Management System）。

基于 Web 统一管理 QEMU 上的 OpenWrt 固件实例：生命周期、控制台、宿主机/访客机双栏文件浏览与 SCP 传输。

## 架构要点

- 全宿主机原生运行（无 Docker）
- SQLite3 + Redis + Celery
- QEMU：TAP + 网桥（参考 `/home/kali/openwrt/armv8/start.sh`）
- OpenWrt ARMv8 seed 模板；支持多实例（同网段 IP 分配或独立网桥）

## 快速开始

```bash
# 克隆时带上子模块（iot-tools）
git clone --recurse-submodules https://github.com/liert/FSEMS.git
cd FSEMS
# 若已克隆未带子模块：
# git submodule update --init --recursive

# 安装系统依赖
sudo apt update
sudo apt install -y qemu-system qemu-utils e2fsprogs bridge-utils uml-utilities libguestfs-tools iptables redis-server

# 启动并启用 Redis
sudo systemctl enable --now redis-server

# 配置网络网桥
sudo ./scripts/setup_network.sh

cp .env.example .env
# 编辑 .env：至少设置 FSEMS_GUEST_SSH_PASSWORD
sudo mkdir -p /var/fsems/{data,workspace,kernels,rootfs,mnt}
sudo chown -R "$USER:$USER" /var/fsems

# 后端依赖（含可编辑安装 third_party/iot-tools）
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
```

### iot-tools 子项目

[iot-tools](https://github.com/liert/iot-tools) 位于 `third_party/iot-tools`，与 FSEMS **一起开发**，也可单独作为 CLI 使用。双栏文件传输默认走 iot-tools（legacy `scp -O`，推送时解析 ELF 依赖）；不可用时回退 asyncssh。

```bash
# 开发时改子项目后重装
backend/.venv/bin/pip install -e third_party/iot-tools
backend/.venv/bin/iot-tools scp --help
```

密码认证需安装 `sshpass`。详见 [`third_party/README.md`](third_party/README.md)。

固件文件放入 `data/kernels/` 与 `data/rootfs/`（生产环境 `/var/fsems/kernels/`、`/var/fsems/rootfs/`）。支持 ARMv8、MIPS、MIPSEL、x86_64 等多架构。

```bash
# 开发环境（TAP/guestmount 建议 root 启动后端）
sudo ./scripts/dev_start.sh
# 或手动：sudo backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --app-dir backend
```

开发环境也可使用仓库内 `./data/` 路径（见 `.env.example`）。

### MCP（Streamable HTTP）Agent 管理接口

后端默认在 **`/mcp`** 暴露标准 MCP Streamable HTTP 服务，供 Cursor / Claude 等 Agent 管理实例与模板：

```bash
# 与 API 同进程（默认 MCP_ENABLED=true）
# 端点: http://127.0.0.1:8000/mcp

# 或独立进程
cd backend && .venv/bin/python -m app.mcp_server
# 端点: http://127.0.0.1:8001/mcp
```

工具包括：`list_instances`、`create_instance`、`instance_action`、`delete_instance`、`list_templates` 等。详见 [`docs/mcp.md`](docs/mcp.md)。

### Node.js 环境安装（推荐使用 NVM）

前端构建与运行需要 Node.js 24+ 环境，推荐使用 NVM（Node Version Manager）进行安装与管理，以避免与系统自带的 Node 版本冲突：

```bash
# 下载并安装 nvm：
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash

# 代替重启 shell：
\. "$HOME/.nvm/nvm.sh"

# 下载并安装 Node.js：
nvm install 24

# 验证安装：
node -v
npm -v
```

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
# 1. 安装系统依赖并启用 Redis
sudo apt update
sudo apt install -y qemu-system qemu-utils e2fsprogs bridge-utils uml-utilities libguestfs-tools iptables redis-server
sudo systemctl enable --now redis-server

# 2. 配置网络与执行安装脚本
sudo ./scripts/setup_network.sh
sudo ./scripts/install_production.sh

# 编辑 /etc/fsems/fsems.env 后：
sudo systemctl enable --now fsems-api fsems-celery
```

使用 Nginx 反代 `127.0.0.1:8000` 的 `/api/v1`，并将 `frontend/dist` 作为静态站点；WebSocket 需配置 `/api/v1/instances/` 的 upgrade 头。

默认登录：`admin` / `admin`（见 `.env`，生产环境务必修改）。
