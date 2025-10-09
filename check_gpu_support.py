#!/usr/bin/env python3
"""
检查当前环境的 GPU 支持情况
用于验证 processor.py 是否能启用 GPU 加速
"""

import platform
import sys

def check_environment():
    print("=" * 60)
    print("GPU 支持检查")
    print("=" * 60)
    print()
    
    # 1. 操作系统
    os_name = platform.system()
    print(f"1️⃣  操作系统: {os_name}")
    print(f"   平台: {platform.platform()}")
    print(f"   架构: {platform.machine()}")
    
    is_linux = os_name == 'Linux'
    if is_linux:
        print("   ✓ Linux 系统")
    else:
        print(f"   ⚠️  非 Linux 系统，GPU 加速仅在 Linux 上启用")
    print()
    
    # 2. ONNX Runtime
    print("2️⃣  ONNX Runtime:")
    try:
        import onnxruntime as ort
        print(f"   版本: {ort.__version__}")
        
        providers = ort.get_available_providers()
        print(f"   可用 Providers: {providers}")
        
        has_cuda = 'CUDAExecutionProvider' in providers
        has_tensorrt = 'TensorrtExecutionProvider' in providers
        
        if has_cuda:
            print("   ✓ CUDAExecutionProvider 可用")
        if has_tensorrt:
            print("   ✓ TensorrtExecutionProvider 可用")
        
        if not has_cuda and not has_tensorrt:
            print("   ⚠️  没有 GPU providers")
            print("   提示: 安装 onnxruntime-gpu 以启用 CUDA")
            
    except ImportError:
        print("   ❌ ONNX Runtime 未安装")
        return False
    print()
    
    # 3. PyTorch (可选)
    print("3️⃣  PyTorch (可选):")
    try:
        import torch
        print(f"   版本: {torch.__version__}")
        print(f"   CUDA 可用: {torch.cuda.is_available()}")
        
        if torch.cuda.is_available():
            print(f"   CUDA 版本: {torch.version.cuda}")
            print(f"   GPU 数量: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                print(f"   GPU {i}: {torch.cuda.get_device_name(i)}")
                mem_total = torch.cuda.get_device_properties(i).total_memory / 1024**3
                print(f"          显存: {mem_total:.1f} GB")
    except ImportError:
        print("   ⚠️  PyTorch 未安装")
    print()
    
    # 4. NVIDIA 驱动 (Linux only)
    if is_linux:
        print("4️⃣  NVIDIA 驱动:")
        import subprocess
        try:
            result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
            if result.returncode == 0:
                print("   ✓ nvidia-smi 可用")
                # 提取关键信息
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Driver Version' in line or 'CUDA Version' in line:
                        print(f"   {line.strip()}")
            else:
                print("   ❌ nvidia-smi 无法运行")
        except FileNotFoundError:
            print("   ❌ nvidia-smi 未找到")
            print("   提示: 需要安装 NVIDIA 驱动")
        print()
    
    # 5. 最终判断
    print("=" * 60)
    print("📊 最终结果:")
    print("=" * 60)
    
    gpu_enabled = is_linux and (has_cuda or has_tensorrt)
    
    if gpu_enabled:
        print("✅ GPU 加速将被启用")
        print()
        print("预期日志输出:")
        print("  - ✓ CUDA Execution Provider detected")
        print("  - Hardware acceleration: CUDA available")
        print("  - 🚀 Enabling GPU acceleration for audio separation")
        print("  - ✅ UVR model loaded successfully with GPU acceleration")
    else:
        print("⚠️  GPU 加速不会启用")
        print()
        print("原因:")
        if not is_linux:
            print("  - 非 Linux 系统")
        if not (has_cuda or has_tensorrt):
            print("  - 没有 GPU Execution Providers")
        print()
        print("预期日志输出:")
        print("  - GPU providers not available, using CPU")
        print("  - Hardware acceleration: CPU only")
        print("  - Running on CPU mode")
        print("  - ✅ UVR model loaded successfully (CPU mode)")
    
    print()
    print("=" * 60)
    
    # 6. 改进建议
    if not gpu_enabled:
        print()
        print("💡 启用 GPU 加速的步骤:")
        print()
        if not is_linux:
            print("1. 在 Linux 系统上部署")
            print("   (GPU 加速目前仅在 Linux 上启用)")
        else:
            print("1. 安装 NVIDIA 驱动和 CUDA:")
            print("   curl -O https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.0-1_all.deb")
            print("   sudo dpkg -i cuda-keyring_1.0-1_all.deb")
            print("   sudo apt-get update")
            print("   sudo apt-get install cuda")
            print()
            print("2. 安装 GPU 版本的依赖:")
            print("   pip uninstall onnxruntime")
            print("   pip install onnxruntime-gpu")
            print()
            print("3. 验证安装:")
            print("   python3 check_gpu_support.py")
            print()
            print("4. 重启服务:")
            print("   ./stop_local.sh")
            print("   ./start_local.sh")
    
    return gpu_enabled

if __name__ == '__main__':
    try:
        enabled = check_environment()
        sys.exit(0 if enabled else 1)
    except Exception as e:
        print(f"\n❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
