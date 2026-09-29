"""
scripts/download_hf_model.py - 预下载 HuggingFace 嵌入模型到本地
用于无法直接访问 huggingface.co 的机器，提前在可联网环境下载后复制到项目 models/ 目录。
"""

import os
import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from huggingface_hub import snapshot_download, HfApi
    _HAS_HF_HUB = True
except Exception:
    _HAS_HF_HUB = False


def parse_args():
    ap = argparse.ArgumentParser(description="下载 HuggingFace 嵌入模型到本地 models/ 目录")
    ap.add_argument("--model", default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", help="HuggingFace 模型 ID")
    ap.add_argument("--target-dir", default=str(PROJECT_ROOT / "models" / "hf"), help="本地保存目录")
    ap.add_argument("--mirror", default=None, help="HuggingFace 镜像地址，例如 https://hf-mirror.com")
    ap.add_argument("--token", default=None, help="HuggingFace Token（如需私有模型）")
    ap.add_argument("--verify", action="store_true", help="仅验证模型是否已缓存")
    return ap.parse_args()


def main():
    args = parse_args()
    if not _HAS_HF_HUB:
        print("❌ 未安装 huggingface_hub，请先: pip install huggingface_hub")
        sys.exit(1)

    if args.mirror:
        os.environ.setdefault("HF_ENDPOINT", args.mirror)

    target_dir = Path(args.target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.verify:
            print(f"✅ 模型检查目标目录: {target_dir}")
            print(f"ℹ️ 若后续启动报网络错误，请使用 --mirror 或手动下载到该目录。")
            return 0

        print(f"📦 正在下载模型: {args.model}")
        print(f"📂 保存到: {target_dir}")
        repo_path = snapshot_download(
            repo_id=args.model,
            local_dir=str(target_dir),
            local_dir_use_symlinks=False,
            token=args.token,
        )
        print(f"✅ 下载完成: {repo_path}")
        return 0
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
