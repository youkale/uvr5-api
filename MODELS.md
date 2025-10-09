# UVR 模型管理指南

本文档介绍如何下载和管理 UVR 音频分离模型。

## 📦 模型目录

默认情况下，模型保存在项目根目录的 `models/` 文件夹中。

可以通过环境变量 `MODEL_FILE_DIR` 自定义模型目录：

```bash
# 在 .env 文件中配置
MODEL_FILE_DIR=./models
```

## 🚀 快速下载

### 方式一：使用 Python 脚本（推荐）

```bash
# 下载默认模型 (UVR-MDX-NET-Inst_HQ_4)
python3 download_models.py

# 或使用 shell 包装器
./download_models.sh
```

### 方式二：使用 uv（如果已安装）

```bash
uv run python download_models.py
```

## 📋 可用模型

| 模型名称 | 大小 | 说明 |
|---------|------|------|
| **UVR-MDX-NET-Inst_HQ_4** | ~200 MB | 高质量乐器分离模型（推荐，默认） |
| UVR-MDX-NET-Inst_HQ_3 | ~200 MB | 高质量乐器分离模型 v3 |
| UVR_MDXNET_KARA_2 | ~200 MB | Karaoke 人声分离模型 |
| Kim_Vocal_2 | ~200 MB | Kim 人声分离模型 |

### 查看所有可用模型

```bash
python3 download_models.py --list
```

输出示例：
```
📋 可用的 UVR 模型:
======================================================================

模型名称: UVR-MDX-NET-Inst_HQ_4
  大小:   200 MB
  说明:   高质量乐器分离模型（推荐）

模型名称: UVR-MDX-NET-Inst_HQ_3
  大小:   200 MB
  说明:   高质量乐器分离模型 v3
...
```

## 📥 下载选项

### 1. 下载默认模型

```bash
python3 download_models.py
```

### 2. 下载指定模型

```bash
python3 download_models.py --model UVR_MDXNET_KARA_2
```

### 3. 下载所有模型

```bash
python3 download_models.py --all
```

### 4. 指定下载目录

```bash
python3 download_models.py --dir /path/to/models
```

### 5. 强制重新下载

```bash
python3 download_models.py --force
```

### 6. 组合使用

```bash
# 下载所有模型到自定义目录并强制覆盖
python3 download_models.py --all --dir /data/models --force
```

## 🔧 命令行参数

```bash
python3 download_models.py [选项]

选项:
  -h, --help            显示帮助信息
  -l, --list            列出所有可用模型
  -m MODEL, --model MODEL
                        下载指定模型
  -a, --all             下载所有模型
  -d DIR, --dir DIR     指定模型目录 (默认: ./models)
  -f, --force           强制重新下载已存在的模型
```

## 📝 使用示例

### 示例 1：首次使用

```bash
# 1. 查看可用模型
python3 download_models.py --list

# 2. 下载默认模型
python3 download_models.py

# 3. 启动服务
./start_local.sh
```

### 示例 2：切换模型

```bash
# 1. 下载新模型
python3 download_models.py --model UVR_MDXNET_KARA_2

# 2. 修改 .env 文件
MODEL_NAME=UVR_MDXNET_KARA_2

# 3. 重启服务
./restart_local.sh
```

### 示例 3：准备离线环境

```bash
# 下载所有模型到指定目录
python3 download_models.py --all --dir /offline/models

# 打包模型目录
tar -czf uvr_models.tar.gz /offline/models

# 在离线环境解压
tar -xzf uvr_models.tar.gz
```

## 🔍 验证模型

### 检查模型文件

```bash
# 列出已下载的模型
ls -lh models/

# 输出示例:
# -rw-r--r--  1 user  staff   200M  Oct 9 12:00 UVR-MDX-NET-Inst_HQ_4.onnx
```

### 验证模型完整性

```bash
# 检查文件大小（应该在 150-250 MB 之间）
du -sh models/*.onnx
```

## 🐛 故障排除

### 问题 1：下载速度慢

模型托管在 GitHub，如果下载慢可以：

1. **使用代理**
```bash
export https_proxy=http://your-proxy:port
python3 download_models.py
```

2. **使用 GitHub 镜像站点**（需要修改脚本中的 URL）

3. **手动下载**
   - 访问 [UVR Model Repository](https://github.com/TRvlvr/model_repo/releases)
   - 下载对应的 `.onnx` 文件
   - 放到 `models/` 目录

### 问题 2：下载中断

脚本会自动清理不完整的文件，重新运行即可：

```bash
python3 download_models.py
```

### 问题 3：权限错误

```bash
# 给脚本执行权限
chmod +x download_models.py download_models.sh

# 或者使用 python3 直接运行
python3 download_models.py
```

### 问题 4：依赖缺失

```bash
# 安装必要的依赖
pip3 install tqdm requests python-dotenv

# 或使用 requirements.txt
pip3 install -r requirements.txt
```

### 问题 5：磁盘空间不足

每个模型约 200 MB，确保有足够空间：

```bash
# 检查磁盘空间
df -h

# 只下载需要的模型
python3 download_models.py --model UVR-MDX-NET-Inst_HQ_4
```

## 🔄 模型更新

### 检查更新

定期查看 [UVR Model Repository](https://github.com/TRvlvr/model_repo) 获取最新模型。

### 更新现有模型

```bash
# 强制重新下载
python3 download_models.py --model MODEL_NAME --force
```

## 📊 模型性能对比

| 模型 | 质量 | 速度 | 内存占用 | 适用场景 |
|------|------|------|---------|---------|
| UVR-MDX-NET-Inst_HQ_4 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ~4GB | 通用、高质量 |
| UVR-MDX-NET-Inst_HQ_3 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ~3GB | 通用 |
| UVR_MDXNET_KARA_2 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ~3GB | Karaoke |
| Kim_Vocal_2 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ~3GB | 人声分离 |

## 🎯 最佳实践

### 1. 生产环境

```bash
# 提前下载所需模型
python3 download_models.py --model UVR-MDX-NET-Inst_HQ_4

# 验证模型完整性
ls -lh models/UVR-MDX-NET-Inst_HQ_4.onnx
```

### 2. 开发环境

```bash
# 下载多个模型用于测试
python3 download_models.py --all
```

### 3. CI/CD

```yaml
# .github/workflows/deploy.yml
- name: Download UVR Models
  run: |
    python3 download_models.py --model UVR-MDX-NET-Inst_HQ_4
```

### 4. Docker 构建

```dockerfile
# 在 Dockerfile 中预下载模型
RUN python3 download_models.py --model UVR-MDX-NET-Inst_HQ_4
```

## 📚 相关文档

- [README.md](README.md) - 主文档
- [config.py](config.py) - 配置说明
- [processor.py](processor.py) - 模型使用代码

## 🔗 外部资源

- [UVR5 官方仓库](https://github.com/Anjok07/ultimatevocalremovergui)
- [UVR 模型仓库](https://github.com/TRvlvr/model_repo)
- [audio-separator 文档](https://github.com/nomadkaraoke/python-audio-separator)

---

## 总结

### 快速开始流程

```bash
# 1. 查看可用模型
python3 download_models.py --list

# 2. 下载默认模型
python3 download_models.py

# 3. 验证下载
ls -lh models/

# 4. 启动服务
./start_local.sh

# 5. 测试 API
./test_api.sh
```

现在你已经掌握了 UVR 模型的下载和管理！🎉
