#!/usr/bin/env python3
"""
UVR 模型下载脚本
支持下载多个 UVR 模型到指定目录
"""

import os
import sys
import argparse
import requests
from pathlib import Path
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("提示: 安装 tqdm 可以显示下载进度: pip install tqdm")

try:
    from audio_separator.separator import Separator
    HAS_AUDIO_SEPARATOR = True
except ImportError:
    HAS_AUDIO_SEPARATOR = False
    print("警告: audio-separator 未安装，将使用手动下载模式")

import config

# 可用的模型列表
AVAILABLE_MODELS = {
    'UVR-MDX-NET-Inst_HQ_4': {
        'url': 'https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/UVR-MDX-NET-Inst_HQ_4.onnx',
        'size': '200 MB',
        'description': '高质量乐器分离模型（推荐）'
    },
    'UVR-MDX-NET-Inst_HQ_3': {
        'url': 'https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/UVR-MDX-NET-Inst_HQ_3.onnx',
        'size': '200 MB',
        'description': '高质量乐器分离模型 v3'
    },
    'UVR_MDXNET_KARA_2': {
        'url': 'https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/UVR_MDXNET_KARA_2.onnx',
        'size': '200 MB',
        'description': 'Karaoke 人声分离模型'
    },
    'Kim_Vocal_2': {
        'url': 'https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/Kim_Vocal_2.onnx',
        'size': '200 MB',
        'description': 'Kim 人声分离模型'
    },
}


def download_file(url: str, output_path: Path, model_name: str):
    """
    下载文件并显示进度条

    Args:
        url: 下载地址
        output_path: 保存路径
        model_name: 模型名称
    """
    try:
        print(f"\n📥 开始下载 {model_name}...")
        print(f"   URL: {url}")
        print(f"   保存到: {output_path}")

        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        # 获取文件大小
        total_size = int(response.headers.get('content-length', 0))

        # 创建进度条
        if HAS_TQDM:
            with open(output_path, 'wb') as f, tqdm(
                desc=model_name,
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    size = f.write(chunk)
                    pbar.update(size)
        else:
            # 无进度条模式
            with open(output_path, 'wb') as f:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r   下载进度: {percent:.1f}%", end='', flush=True)
            print()  # 换行

        print(f"✅ {model_name} 下载完成")
        return True

    except requests.exceptions.RequestException as e:
        print(f"❌ 下载失败: {str(e)}")
        # 删除不完整的文件
        if output_path.exists():
            output_path.unlink()
        return False
    except Exception as e:
        print(f"❌ 发生错误: {str(e)}")
        if output_path.exists():
            output_path.unlink()
        return False


def download_with_audio_separator(model_name: str, model_dir: Path):
    """
    使用 audio-separator 内置功能下载模型

    Args:
        model_name: 模型名称（不带扩展名）
        model_dir: 模型目录
    """
    try:
        print(f"\n📥 使用 audio-separator 下载 {model_name}...")

        # 创建 Separator 实例
        separator = Separator(
            log_level=30,  # WARNING level
            model_file_dir=str(model_dir),
            output_dir=str(model_dir)
        )

        # 尝试加载模型，如果不存在会自动下载
        model_filename = model_name if model_name.endswith('.onnx') else f"{model_name}.onnx"
        separator.load_model(model_filename)

        print(f"✅ {model_name} 下载/加载完成")
        return True

    except Exception as e:
        print(f"❌ audio-separator 下载失败: {str(e)}")
        return False


def list_models():
    """列出所有可用的模型"""
    print("\n📋 可用的 UVR 模型:")
    print("=" * 70)
    for model_name, info in AVAILABLE_MODELS.items():
        print(f"\n模型名称: {model_name}")
        print(f"  大小:   {info['size']}")
        print(f"  说明:   {info['description']}")
    print("\n" + "=" * 70)


def check_model_exists(model_name: str, model_dir: Path) -> bool:
    """检查模型是否已存在"""
    model_path = model_dir / f"{model_name}.onnx"
    if model_path.exists():
        file_size = model_path.stat().st_size
        size_mb = file_size / (1024 * 1024)
        print(f"✓ {model_name} 已存在 ({size_mb:.1f} MB)")
        return True
    return False


def download_model(model_name: str, model_dir: Path, force: bool = False):
    """
    下载指定模型

    Args:
        model_name: 模型名称
        model_dir: 模型目录
        force: 是否强制重新下载
    """
    # 检查模型是否已存在
    model_path = model_dir / f"{model_name}.onnx"
    if model_path.exists() and not force:
        print(f"\n✓ {model_name} 已存在")
        print(f"  路径: {model_path}")
        print(f"  使用 --force 强制重新下载")
        return True

    # 方式1: 优先使用 audio-separator 内置下载（支持更多模型）
    if HAS_AUDIO_SEPARATOR:
        if download_with_audio_separator(model_name, model_dir):
            return True
        print("   尝试手动下载...")

    # 方式2: 手动下载（仅支持列表中的模型）
    if model_name not in AVAILABLE_MODELS:
        print(f"❌ 模型 {model_name} 无法通过手动下载")
        print(f"   请安装 audio-separator 或使用以下模型之一:")
        for name in AVAILABLE_MODELS.keys():
            print(f"   - {name}")
        return False

    # 下载模型
    model_info = AVAILABLE_MODELS[model_name]
    return download_file(model_info['url'], model_path, model_name)


def download_all_models(model_dir: Path, force: bool = False):
    """下载所有模型"""
    print(f"\n📦 准备下载所有模型到: {model_dir}")

    success_count = 0
    total_count = len(AVAILABLE_MODELS)

    for model_name in AVAILABLE_MODELS.keys():
        if download_model(model_name, model_dir, force):
            success_count += 1

    print(f"\n{'=' * 70}")
    print(f"下载完成: {success_count}/{total_count} 个模型成功")
    print(f"{'=' * 70}")

    return success_count == total_count


def main():
    parser = argparse.ArgumentParser(
        description='UVR 模型下载工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出所有可用模型
  python download_models.py --list

  # 下载默认模型 (UVR-MDX-NET-Inst_HQ_4)
  python download_models.py

  # 下载指定模型
  python download_models.py --model UVR_MDXNET_KARA_2

  # 下载所有模型
  python download_models.py --all

  # 指定模型目录
  python download_models.py --dir /path/to/models

  # 强制重新下载
  python download_models.py --force
        """
    )

    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='列出所有可用的模型'
    )

    parser.add_argument(
        '--model', '-m',
        type=str,
        help='要下载的模型名称'
    )

    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='下载所有可用的模型'
    )

    parser.add_argument(
        '--dir', '-d',
        type=str,
        default=config.MODEL_FILE_DIR,
        help=f'模型保存目录 (默认: {config.MODEL_FILE_DIR})'
    )

    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='强制重新下载已存在的模型'
    )

    args = parser.parse_args()

    # 列出模型
    if args.list:
        list_models()
        return 0

    # 创建模型目录
    model_dir = Path(args.dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🎵 UVR 模型下载工具")
    print(f"模型目录: {model_dir.absolute()}")

    # 下载所有模型
    if args.all:
        success = download_all_models(model_dir, args.force)
        return 0 if success else 1

    # 下载指定模型
    if args.model:
        success = download_model(args.model, model_dir, args.force)
        return 0 if success else 1

    # 默认下载配置的模型
    default_model = config.MODEL_NAME
    print(f"\n使用默认模型: {default_model}")
    print("提示: 使用 --list 查看所有可用模型")

    success = download_model(default_model, model_dir, args.force)

    if success:
        print(f"\n✅ 模型已准备就绪")
        print(f"   模型: {default_model}")
        print(f"   路径: {model_dir / f'{default_model}.onnx'}")
        print(f"\n💡 现在可以启动服务:")
        print(f"   ./start_local.sh  # 本地运行")
        print(f"   ./start.sh        # Docker 运行")
        return 0
    else:
        return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  下载已取消")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {str(e)}")
        sys.exit(1)
