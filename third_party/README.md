# third_party

子项目 / Git 子模块。与 FSEMS **一体开发**：在本树内改代码，有问题直接修；同时可独立安装、独立运行。

| 路径 | 仓库 | 用途 |
| :--- | :--- | :--- |
| [`iot-tools`](./iot-tools) | https://github.com/liert/iot-tools.git | 简化 IoT 指令：智能 SCP、ELF 依赖、符号查找等 |

## 开发模式（推荐）

在 FSEMS 仓库内直接改子模块：

```bash
cd third_party/iot-tools
# 编辑 src/iot_tools/...
# 可编辑安装后立刻被 backend/Celery 使用：
cd ../../backend && .venv/bin/pip install -e ../third_party/iot-tools

# 单独作为 CLI 验证
.venv/bin/iot-tools scp --help
.venv/bin/iot-tools scp ./app root@192.168.1.1:/usr/bin/app

# 提交子项目并推远端
cd ../third_party/iot-tools
git add -A && git commit -m "feat: ..."
git push origin main

# 父仓库记录新的 submodule 指针
cd ../..
git add third_party/iot-tools
git commit -m "chore: bump iot-tools"
```

FSEMS 调用入口：`backend/app/services/iot_tools_client.py`（双栏传输默认走 iot-tools）。

## 克隆与更新

```bash
git clone --recurse-submodules https://github.com/liert/FSEMS.git
# 或
git submodule update --init --recursive
```

## 安装

```bash
cd backend
.venv/bin/pip install -r requirements.txt   # 含 -e ../third_party/iot-tools
```

Python 依赖：`asyncssh`（由 `pip install -e` 自动安装）。传输为 legacy SCP（`use_sftp=False`），无需系统 `scp`/`sshpass`。
