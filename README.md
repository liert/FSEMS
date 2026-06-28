# FSEMS

固件模拟环境管理系统（Firmware Simulation Environment Management System）。

基于 Web 统一管理 QEMU 上的 OpenWrt 固件实例：生命周期、串口控制台、宿主机/访客机双栏文件浏览与 SCP 传输。

## 文档

| 文件 | 说明 |
| :--- | :--- |
| [AGENTS.md](AGENTS.md) | AI 编码代理指南 |
| [docs/FSEMS_development_document.md](docs/FSEMS_development_document.md) | 完整开发规格 |

## 架构要点

- 全宿主机原生运行（无 Docker）
- SQLite3 + Redis + Celery
- QEMU：TAP + 网桥（参考 `/home/kali/openwrt/armv8/start.sh`）
- Phase 1：OpenWrt ARMv8 单实例

## 快速开始

```bash
sudo ./scripts/install_host_deps.sh
sudo ./scripts/setup_network.sh
cp .env.example .env
sudo mkdir -p /var/fsems/{data,workspace,images,kernels,mnt}
sudo chown -R "$USER:$USER" /var/fsems
```

固件文件放入 `/var/fsems/kernels/` 与 `/var/fsems/images/`（文件名见开发文档 §4.4）。

```bash
# 实现 backend/ 与 frontend/ 后：
./scripts/dev_start.sh
```

## 实现顺序

Phase 1 分步编码指南见开发文档 [§13](docs/FSEMS_development_document.md#13-phase-1-编码顺序建议)。

## 状态

**Phase 1 后端与前端骨架已实现。** 启动方式：

```bash
# 终端 1 — 后端
cd backend && source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --app-dir .

# 终端 2 — 前端
cd frontend && npm run dev
```

默认登录：`admin` / `admin`（见 `.env`）。
