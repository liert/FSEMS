# third_party

Git 子模块与外部工具仓库。

| 路径 | 仓库 | 用途 |
| :--- | :--- | :--- |
| [`iot-tools`](./iot-tools) | https://github.com/liert/iot-tools.git | IoT 智能 SCP（ELF + NEEDED 依赖）、符号查找等 |

## 克隆与更新

```bash
# 首次克隆 FSEMS
git clone --recurse-submodules https://github.com/liert/FSEMS.git

# 已克隆但未拉子模块
git submodule update --init --recursive

# 更新 iot-tools 到远端最新 main
cd third_party/iot-tools
git fetch origin
git checkout main
git pull origin main
cd ../..
git add third_party/iot-tools
git commit -m "chore: bump iot-tools submodule"
```

## 安装到后端 venv

在仓库根目录或 backend 下：

```bash
cd backend
.venv/bin/pip install -e ../third_party/iot-tools
# 或：pip install -r requirements.txt  （requirements 中已包含 -e 路径）
```

验证：

```bash
.venv/bin/iot-tools --help
# 或
.venv/bin/python -m iot_tools --help
```
