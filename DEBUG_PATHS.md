# 文件路径调试指南

## 问题分析

根据错误日志：
```
ERROR - Unexpected upload error: [Errno 2] No such file or directory:
'2e5eb0ab-7808-49e9-a009-34d61c14f967_input_(Vocals)_UVR-MDX-NET-Inst_HQ_4.wav'
```

但文件实际存在于 `output/` 目录：
```bash
output/2e5eb0ab-7808-49e9-a009-34d61c14f967_input_(Vocals)_UVR-MDX-NET-Inst_HQ_4.wav
```

## 根本原因

`audio-separator` 的 `separate()` 方法返回的文件路径可能是：
1. 相对路径（只是文件名）
2. 相对于输出目录的路径
3. 绝对路径

需要确保 processor.py 返回的是**完整的绝对路径**。

## 已修复的内容

### processor.py - `_separate_audio()` 方法

```python
# 修复前：直接使用 audio-separator 返回的路径
vocals_path = file_path  # 可能只是文件名

# 修复后：确保使用完整路径
if not os.path.isabs(file_path):
    full_path = os.path.join(config.OUTPUT_DIR, file_path)
    if not os.path.exists(full_path):
        full_path = file_path  # 回退
else:
    full_path = file_path

# 验证文件存在
if not os.path.exists(vocals_path):
    raise Exception(f"Vocals file not found: {vocals_path}")
```

## 验证步骤

### 1. 检查 processor 日志

重启后应该看到：
```
INFO - [task_uuid] Vocals: /full/path/to/output/xxx_vocals.wav
INFO - [task_uuid] Instrumental: /full/path/to/output/xxx_instrumental.wav
```

### 2. 验证文件路径

```bash
# 在 processor 处理完成后
ls -la output/

# 应该看到文件
```

### 3. 检查 uploader 日志

```
INFO - Uploading /full/path/to/xxx_vocals.wav to S3 as xxx_vocals.wav
```

## 测试命令

```bash
# 1. 停止服务
./stop_local.sh

# 2. 清理旧文件
rm -rf output/* temp/*

# 3. 重启服务
./start_local.sh

# 4. 发送测试请求
curl -X POST http://localhost:8000/generate \
  -u admin:password \
  -H "Content-Type: application/json" \
  -d '{
    "audio": "https://example.com/audio.wav",
    "hook_url": "https://example.com/webhook"
  }'

# 5. 实时查看日志
tail -f logs/processor.log logs/uploader.log
```

## 预期日志输出

### Processor 日志（processor.log）

```
INFO - [xxx] Processing task
INFO - [xxx] Downloading audio from https://...
INFO - [xxx] Audio downloaded: ./temp/xxx_input.wav
INFO - [xxx] Starting audio separation
INFO - [xxx] Separation complete. Output files: [...]
INFO - [xxx] Vocals: /workspace/uvr5-api/output/xxx_input_(Vocals)_UVR-MDX-NET-Inst_HQ_4.wav
INFO - [xxx] Instrumental: /workspace/uvr5-api/output/xxx_input_(Instrumental)_UVR-MDX-NET-Inst_HQ_4.wav
INFO - [xxx] Success result sent to result topic
INFO - [xxx] Cleaned up input file
```

### Uploader 日志（uploader.log）

```
INFO - Received result: xxx (success: True)
INFO - [xxx] Processing success result
INFO - Uploading /workspace/uvr5-api/output/xxx_input_(Vocals)_UVR-MDX-NET-Inst_HQ_4.wav to S3 as xxx_vocals.wav
INFO - File uploaded: https://...
INFO - Uploading /workspace/uvr5-api/output/xxx_input_(Instrumental)_UVR-MDX-NET-Inst_HQ_4.wav to S3 as xxx_instrumental.wav
INFO - File uploaded: https://...
INFO - Sending webhook to https://...
INFO - Webhook sent successfully
INFO - [xxx] Success callback sent
INFO - Cleaned up: /workspace/uvr5-api/output/xxx_input_(Vocals)_UVR-MDX-NET-Inst_HQ_4.wav
INFO - Cleaned up: /workspace/uvr5-api/output/xxx_input_(Instrumental)_UVR-MDX-NET-Inst_HQ_4.wav
```

## 如果问题仍存在

### 调试步骤

1. **在 processor.py 中添加调试日志**：

```python
# 在 _separate_audio 方法中
for file_path in output_files:
    logger.info(f"DEBUG - Raw output file: {file_path}")
    logger.info(f"DEBUG - Is absolute: {os.path.isabs(file_path)}")
    logger.info(f"DEBUG - Exists: {os.path.exists(file_path)}")
```

2. **检查当前工作目录**：

```bash
# 在服务运行时
ps aux | grep processor.py
# 查看工作目录
lsof -p <PID> | grep cwd
```

3. **手动测试 audio-separator**：

```python
from audio_separator.separator import Separator
import os

sep = Separator(
    model_file_dir='./models',
    output_dir='./output'
)
sep.load_model('UVR-MDX-NET-Inst_HQ_4.onnx')

files = sep.separate('./test_input.wav')
print(f"Output files: {files}")
for f in files:
    print(f"  {f} - exists: {os.path.exists(f)}")
```

## 配置检查

确保 `.env` 文件配置正确：

```bash
OUTPUT_DIR=./output  # 或绝对路径 /workspace/uvr5-api/output
TEMP_DIR=./temp
MODEL_FILE_DIR=./models
```

## 重启服务

```bash
./restart_local.sh
```

---

修复后，上传应该能正确找到文件并成功上传到 S3。
