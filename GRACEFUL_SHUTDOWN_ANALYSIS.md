# Kafka Consumer 优雅退出分析

## 当前实现检查

### ✅ 已实现的功能

#### processor.py
```python
def start(self):
    try:
        for message in self.consumer:
            # 处理消息
            ...
    except KeyboardInterrupt:
        logger.info("Processor interrupted by user")  # ✓ 捕获 Ctrl+C
    except Exception as e:
        logger.error(f"Processor error: {str(e)}")
        raise
    finally:
        self.close()  # ✓ 确保调用 close

def close(self):
    if self.consumer:
        self.consumer.close()  # ✓ 关闭 consumer
    if self.producer:
        self.producer.close()  # ✓ 关闭 producer
    logger.info("Processor connections closed")
```

#### uploader.py
```python
def start(self):
    try:
        for message in self.consumer:
            # 处理消息
            ...
    except KeyboardInterrupt:
        logger.info("Uploader interrupted by user")  # ✓ 捕获 Ctrl+C
    except Exception as e:
        logger.error(f"Uploader error: {str(e)}")
        raise
    finally:
        self.close()  # ✓ 确保调用 close

def close(self):
    if self.consumer:
        self.consumer.close()  # ✓ 关闭 consumer
    logger.info("Uploader connections closed")
```

#### app.py
```python
def shutdown_handler():
    global kafka_producer
    if kafka_producer:
        kafka_producer.close()  # ✓ 关闭 producer
        logger.info("Kafka producer closed")

if __name__ == '__main__':
    import atexit
    atexit.register(shutdown_handler)  # ✓ 注册退出处理器
```

### ⚠️ 存在的问题

#### 1. 缺少信号处理器 (SIGTERM)

**问题**:
- 只捕获 `KeyboardInterrupt` (SIGINT/Ctrl+C)
- 没有处理 `SIGTERM` 信号（Docker、systemd 等使用）
- `stop_local.sh` 使用 `kill` 命令发送 SIGTERM

**影响**:
- SIGTERM 信号会立即终止进程
- Consumer 可能没有机会提交 offset
- 可能导致消息重复处理

#### 2. enable_auto_commit=True 但没有显式提交

**当前配置** (processor.py & uploader.py):
```python
self.consumer = KafkaConsumer(
    ...
    enable_auto_commit=True  # ← 自动提交
)

# 但日志中有:
logger.info(f"[{task_uuid}] Offset committed successfully")
# 这行日志输出但没有实际的 commit() 调用
```

**问题**:
- 代码中没有 `self.consumer.commit()` 调用
- 依赖自动提交机制
- 自动提交间隔默认 5 秒
- 如果在两次自动提交之间退出，offset 可能丢失

#### 3. 没有等待消息处理完成

**当前实现**:
```python
try:
    for message in self.consumer:
        self._process_task(task_data)  # 可能需要几分钟
        # 如果这时收到 SIGTERM...
except KeyboardInterrupt:
    self.close()  # 立即关闭，不等待任务完成
```

**问题**:
- 任务处理到一半可能被打断
- 音频分离是长时间操作 (30秒-3分钟)
- 没有优雅关闭的等待期

#### 4. Consumer 关闭顺序

**当前实现**:
```python
def close(self):
    if self.consumer:
        self.consumer.close()  # 直接关闭
    if self.producer:
        self.producer.close()
```

**建议**:
- 先停止接收新消息
- 等待当前消息处理完成
- 提交 offset
- 关闭连接

## 推荐的改进方案

### 改进 1: 添加信号处理器

```python
import signal
import sys

class UVRProcessor:
    def __init__(self):
        self.separator = None
        self.consumer = None
        self.producer = None
        self.shutdown_flag = False  # 添加关闭标志

        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self._load_model()
        self._connect_kafka()

    def _signal_handler(self, signum, frame):
        """处理关闭信号"""
        sig_name = 'SIGTERM' if signum == signal.SIGTERM else 'SIGINT'
        logger.info(f"Received {sig_name}, starting graceful shutdown...")
        self.shutdown_flag = True
```

### 改进 2: 优雅关闭循环

```python
def start(self):
    """Start consuming and processing tasks"""
    logger.info("UVR Processor started, waiting for tasks...")

    try:
        for message in self.consumer:
            # 检查关闭标志
            if self.shutdown_flag:
                logger.info("Shutdown flag set, stopping message consumption")
                break

            try:
                task_data = message.value
                task_uuid = task_data.get('task_uuid', 'unknown')
                logger.info(f"Received task: {task_uuid}")

                # 处理任务
                self._process_task(task_data)

                # 显式提交 offset
                self.consumer.commit()
                logger.info(f"[{task_uuid}] Offset committed successfully")

            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"Processor error: {str(e)}")
        raise
    finally:
        logger.info("Cleaning up and closing connections...")
        self.close()
```

### 改进 3: 更安全的 close 方法

```python
def close(self):
    """Close connections gracefully"""
    logger.info("Starting graceful shutdown...")

    try:
        # 1. 停止接收新消息（通过 shutdown_flag，已在循环中处理）

        # 2. 提交 offset（如果使用手动提交）
        if self.consumer and hasattr(self.consumer, 'commit'):
            try:
                logger.info("Committing final offsets...")
                self.consumer.commit()
                logger.info("Final offsets committed")
            except Exception as e:
                logger.warning(f"Failed to commit final offsets: {e}")

        # 3. 关闭 consumer
        if self.consumer:
            try:
                logger.info("Closing Kafka consumer...")
                self.consumer.close()
                logger.info("Kafka consumer closed")
            except Exception as e:
                logger.error(f"Error closing consumer: {e}")

        # 4. 关闭 producer
        if self.producer:
            try:
                logger.info("Closing Kafka producer...")
                # Flush 未发送的消息
                self.producer.flush(timeout=10)
                self.producer.close()
                logger.info("Kafka producer closed")
            except Exception as e:
                logger.error(f"Error closing producer: {e}")

        logger.info("Processor shutdown complete")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
```

### 改进 4: 处理中断时的任务状态

```python
def _process_task(self, task_data):
    """Process a single task"""
    task_uuid = task_data['task_uuid']
    audio_path = task_data['audio_path']
    hook_url = task_data['hook_url']

    vocals_path = None
    instrumental_path = None

    try:
        # 在处理前检查关闭标志
        if self.shutdown_flag:
            logger.warning(f"[{task_uuid}] Shutdown requested, skipping task")
            # 不提交 offset，让任务被重新消费
            raise Exception("Shutdown in progress")

        logger.info(f"[{task_uuid}] Processing task")
        logger.info(f"[{task_uuid}] Audio file: {audio_path}")

        # 验证音频文件存在
        if not os.path.exists(audio_path):
            raise Exception(f"Audio file not found: {audio_path}")

        # Separate audio
        vocals_path, instrumental_path = self._separate_audio(audio_path, task_uuid)

        # 再次检查关闭标志（分离可能需要几分钟）
        if self.shutdown_flag:
            logger.warning(f"[{task_uuid}] Shutdown during processing, marking as incomplete")
            # 发送失败消息，让任务重新处理
            raise Exception("Shutdown during processing")

        # 发送成功结果
        result = {
            'task_uuid': task_uuid,
            'success': True,
            'vocals_path': vocals_path,
            'instrumental_path': instrumental_path,
            'hook_url': hook_url
        }

        self.producer.send(config.KAFKA_RESULT_TOPIC, key=task_uuid, value=result)
        logger.info(f"[{task_uuid}] Success result sent to result topic")

    except Exception as e:
        logger.error(f"[{task_uuid}] Task processing failed: {str(e)}")

        # 发送失败结果
        result = {
            'task_uuid': task_uuid,
            'success': False,
            'error_message': str(e),
            'hook_url': hook_url
        }

        self.producer.send(config.KAFKA_RESULT_TOPIC, key=task_uuid, value=result)
        logger.info(f"[{task_uuid}] Failure result sent to result topic")

    finally:
        # Clean up input file
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f"[{task_uuid}] Cleaned up input file")
            except Exception as e:
                logger.warning(f"[{task_uuid}] Failed to cleanup input file: {e}")
```

## 完整的改进代码示例

### processor.py 增强版

```python
import signal
import sys

class UVRProcessor:
    """UVR audio separation processor with graceful shutdown"""

    def __init__(self):
        """Initialize UVR processor with model loaded once"""
        self.separator = None
        self.consumer = None
        self.producer = None
        self.shutdown_flag = False

        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        self._load_model()
        self._connect_kafka()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        sig_name = 'SIGTERM' if signum == signal.SIGTERM else 'SIGINT'
        logger.info(f"Received {sig_name}, initiating graceful shutdown...")
        self.shutdown_flag = True

    # ... 其他方法保持不变 ...

    def start(self):
        """Start consuming and processing tasks"""
        logger.info("UVR Processor started, waiting for tasks...")

        try:
            for message in self.consumer:
                # 检查关闭标志
                if self.shutdown_flag:
                    logger.info("Shutdown requested, stopping message consumption")
                    break

                try:
                    task_data = message.value
                    task_uuid = task_data.get('task_uuid', 'unknown')
                    logger.info(f"Received task: {task_uuid}")

                    # 处理任务
                    self._process_task(task_data)

                    # 显式提交 offset
                    self.consumer.commit()
                    logger.info(f"[{task_uuid}] Offset committed successfully")

                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}")
                    continue

        except Exception as e:
            if not self.shutdown_flag:
                logger.error(f"Processor error: {str(e)}")
                raise
        finally:
            logger.info("Processor shutting down...")
            self.close()

    def close(self):
        """Close connections gracefully"""
        logger.info("Closing Kafka connections...")

        # 提交最终 offset
        if self.consumer:
            try:
                self.consumer.commit()
                logger.info("Final offset committed")
            except Exception as e:
                logger.warning(f"Failed to commit final offset: {e}")

        # 关闭 consumer
        if self.consumer:
            try:
                self.consumer.close()
                logger.info("Kafka consumer closed")
            except Exception as e:
                logger.error(f"Error closing consumer: {e}")

        # Flush 并关闭 producer
        if self.producer:
            try:
                self.producer.flush(timeout=10)
                self.producer.close()
                logger.info("Kafka producer closed")
            except Exception as e:
                logger.error(f"Error closing producer: {e}")

        logger.info("Processor shutdown complete")
```

## 测试优雅关闭

### 测试步骤

1. **启动服务**
```bash
./start_local.sh
tail -f logs/processor.log
```

2. **发送测试任务**
```bash
./test_api.sh
```

3. **在处理过程中停止服务**
```bash
# 使用 SIGTERM (推荐)
./stop_local.sh

# 或使用 SIGINT
# 找到进程: ps aux | grep processor.py
# 发送信号: kill -INT <PID>
```

4. **检查日志**
```bash
# 应该看到:
# - "Received SIGTERM, initiating graceful shutdown..."
# - "Shutdown requested, stopping message consumption"
# - "Final offset committed"
# - "Kafka consumer closed"
# - "Kafka producer closed"
# - "Processor shutdown complete"
```

### 验证 Offset 提交

```bash
# 查看 consumer group 状态
python3 << 'EOF'
from kafka.admin import KafkaAdminClient
from kafka import KafkaConsumer
import config

admin = KafkaAdminClient(bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS.split(','))

# 查看 processor group 的 offset
consumer = KafkaConsumer(
    config.KAFKA_TASK_TOPIC,
    bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS.split(','),
    group_id=config.KAFKA_PROCESSOR_GROUP_ID
)

# 获取已提交的 offset
committed = consumer.committed(list(consumer.assignment())[0])
print(f"Last committed offset: {committed}")

consumer.close()
admin.close()
EOF
```

## 监控和调试

### 检查优雅关闭

```bash
# 查看关闭日志
grep -E "shutdown|SIGTERM|SIGINT|closing|closed" logs/processor.log | tail -20

# 查看 offset 提交
grep "offset committed" logs/processor.log | tail -10

# 查看是否有未处理完的任务
grep "Shutdown during processing" logs/processor.log
```

### 常见问题

#### Q1: 服务无法停止

**原因**: 可能在处理长时间任务
**解决**:
```bash
# 等待任务完成（最多 10 分钟）
timeout 600 ./stop_local.sh

# 如果还是无法停止，强制终止
kill -9 $(cat .pids/processor.pid)
```

#### Q2: Offset 没有提交

**检查**:
```bash
# 查看是否调用了 commit
grep "commit" logs/processor.log

# 查看是否有 commit 错误
grep "Failed to commit" logs/processor.log
```

#### Q3: 任务被重复处理

**原因**: Offset 没有正确提交
**解决**: 确保 `enable_auto_commit=True` 或显式调用 `commit()`

## 总结

### ✅ 当前实现 (基本功能)
- ✓ 捕获 KeyboardInterrupt
- ✓ Finally 块中调用 close()
- ✓ Close 方法关闭 consumer 和 producer

### ⚠️ 需要改进
- ❌ 没有处理 SIGTERM 信号
- ❌ 没有优雅关闭标志
- ❌ 没有显式提交 offset（依赖自动提交）
- ❌ 没有等待当前任务完成
- ❌ Producer 没有 flush

### 🚀 推荐改进
1. 添加信号处理器 (SIGINT, SIGTERM)
2. 使用 shutdown_flag 优雅停止
3. 显式提交 offset
4. Producer flush before close
5. 检查关闭标志，避免处理到一半被打断
