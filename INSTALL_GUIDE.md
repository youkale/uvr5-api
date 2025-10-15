# 安装指南

## ⚡ 快速安装（推荐）

本项目是应用程序项目，**推荐直接从 requirements 文件安装**：

```bash
# 1. 创建虚拟环境
uv venv

# 2. 激活虚拟环境
source .venv/bin/activate

# 3. 安装依赖
uv pip install -r requirements.txt

# 或 GPU 版本（Linux CUDA）
uv pip install -r requirements-gpu.txt
```

## ❌ 常见错误

### 错误：`pip install -e .` 失败

如果你遇到以下错误：
```
ValueError: Unable to determine which files to ship inside the wheel
```

**解决方案**：不要使用可编辑安装，直接使用 requirements 文件。

本项目是应用程序项目（包含独立的 `.py` 文件），不是标准的 Python 包，因此：

- ✅ **推荐**：`uv pip install -r requirements.txt`
- ❌ **不推荐**：`uv pip install -e .`

## 📦 项目结构说明

本项目是**应用程序项目**，而非 Python 库：

```
uvr_api/
├── app.py              # 独立应用文件
├── processor.py        # 独立应用文件
├── uploader.py         # 独立应用文件
├── config.py           # 配置模块
├── redis_queue.py      # 工具模块
└── requirements.txt    # 依赖文件 ✅
```

**不是**标准的包结构：
```
❌ 这不是本项目的结构
uvr_api/
└── src/
    └── uvr_api/
        ├── __init__.py
        ├── app.py
        └── ...
```

## 🎯 pyproject.toml 的作用

`pyproject.toml` 在本项目中主要用于：

1. **依赖版本管理** - 集中管理所有依赖版本
2. **项目元数据** - 项目名称、版本、描述
3. **工具配置** - 未来可能用于 linter、formatter 等配置

**不用于**：可编辑安装（pip install -e .）

## 🚀 一键启动

最简单的方法是使用启动脚本，它会自动安装依赖：

```bash
./start_local.sh
```

脚本会自动：
1. ✅ 检测 uv 或 pip
2. ✅ 创建虚拟环境
3. ✅ 安装依赖（从 requirements 文件）
4. ✅ 启动所有服务

## 📖 更多信息

- 完整依赖说明：查看 `DEPENDENCIES.md`
- 项目文档：查看 `README.md`
