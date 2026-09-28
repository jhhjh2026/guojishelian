"""
ingest.py - ISSF 2026 规则文档索引管理入口
功能：
1. 自动扫描 data/rules/ 下的所有 Markdown 规则文件
2. 加载 -> 智能切分 -> 向量化 -> 持久化
3. 支持命令行参数：强制重建、自定义目录

使用：
  python -m backend.app.ingest --rebuild
  python -m backend.app.ingest --rules-dir data/rules --persist-dir data/vector_store
"""

import os
import sys
import time
import argparse
import logging
from datetime import datetime, timezone

# 确保项目根目录在 sys.path 中，支持直接运行
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from .config import get_path_config, MODEL_CONFIG
from .utils import setup_logging, load_markdown_documents
from .utils.vector_store_manager import (
    get_or_create_vector_store,
    rebuild_vector_store,
    delete_vector_store,
)
from langchain_community.embeddings import DashScopeEmbeddings

try:
    from langchain_community.embeddings import HuggingFaceEmbeddings
    _HAS_HF_EMBEDDINGS = True
except Exception:
    _HAS_HF_EMBEDDINGS = False


def _build_embeddings():
    provider = getattr(MODEL_CONFIG, "EMBEDDING_PROVIDER", "dashscope").lower()
    if provider == "huggingface" and _HAS_HF_EMBEDDINGS:
        hf_model = MODEL_CONFIG.EMBEDDING_HF_MODEL
        hf_device = getattr(MODEL_CONFIG, "EMBEDDING_HF_DEVICE", "cpu")
        hf_mirror = getattr(MODEL_CONFIG, "EMBEDDING_HF_MIRROR", None)
        hf_local_dir = getattr(MODEL_CONFIG, "EMBEDDING_HF_LOCAL_DIR", None)
        hf_kwargs = {"device": hf_device}
        if hf_mirror:
            os.environ.setdefault("HF_ENDPOINT", hf_mirror)
        effective_model = hf_local_dir if hf_local_dir and os.path.isdir(hf_local_dir) else hf_model
        return HuggingFaceEmbeddings(model_name=effective_model, model_kwargs=hf_kwargs)
    return DashScopeEmbeddings(
        model=MODEL_CONFIG.EMBEDDING_MODEL,
        dashscope_api_key=MODEL_CONFIG.DASHSCOPE_API_KEY,
    )

logger = logging.getLogger("ingest")


def _build_chunk_stats(documents):
    """统计加载文档的信息"""
    file_count = len(documents)
    total_chars = sum(len(doc.page_content) for doc in documents)
    return file_count, total_chars


def run_ingest(rules_dir, persist_dir, force_rebuild=False, show_progress=False):
    """执行索引构建"""
    log_name = "ingest"
    os.makedirs(os.path.dirname(persist_dir) if os.path.dirname(persist_dir) else ".", exist_ok=True)
    logger_inst, _ = setup_logging(log_name=log_name, project_root=_project_root)

    separator = "=" * 60
    print(separator)
    print("📂 ISSF 2026 规则文档 - 向量索引构建")
    print(separator)

    if not os.path.exists(rules_dir):
        print(f"❌ 规则目录不存在: {rules_dir}")
        logger_inst.error(f"规则目录不存在: {rules_dir}")
        return False

    start_ts = time.time()

    # 1. 扫描文档
    try:
        from glob import glob
        md_files = glob(os.path.join(rules_dir, "**/*.md"), recursive=True)
        md_files += glob(os.path.join(rules_dir, "**/*.MD"), recursive=True)
        md_files = sorted(set(md_files))
    except Exception as e:
        print(f"❌ 扫描规则文件失败: {e}")
        logger_inst.error(f"扫描规则文件失败: {e}", exc_info=True)
        return False

    if not md_files:
        print(f"❌ 在 {rules_dir} 下（含子目录）未找到任何 .md 规则文件")
        logger_inst.error(f"在 {rules_dir} 下未找到任何 .md 规则文件")
        return False

    print(f"🔍 扫描完成: 共找到 {len(md_files)} 个规则文件")
    for f in md_files:
        rel = os.path.relpath(f, rules_dir)
        size_kb = os.path.getsize(f) / 1024.0
        print(f"   - {rel} ({size_kb:.1f} KB)")

    logger_inst.info(f"扫描规则目录: {rules_dir}, 找到 {len(md_files)} 个文件")

    # 2. 加载文档
    t0 = time.time()
    print("\n⏳ 正在加载 Markdown 文档...")
    try:
        documents = load_markdown_documents(rules_dir)
    except Exception as e:
        print(f"❌ 加载文档失败: {e}")
        logger_inst.error(f"加载文档失败: {e}", exc_info=True)
        return False
    load_ts = time.time() - t0

    if not documents:
        print("❌ 没有加载到有效文档，请检查规则文件内容")
        logger_inst.error("没有加载到有效文档")
        return False

    file_count, total_chars = _build_chunk_stats(documents)
    print(f"✅ 加载完成: {file_count} 个文件, 共 {total_chars:,} 字符, 耗时 {load_ts:.2f}s")
    logger_inst.info(f"加载完成: {file_count} 文件, {total_chars} 字符, 耗时 {load_ts:.2f}s")

    # 3. 构建向量库
    print("\n⏳ 正在构建向量索引（首次或强制重建可能需要较长时间）...")
    embeddings = _build_embeddings()
    if force_rebuild:
        print("🔄 强制重建: 删除旧向量库...")
        delete_vector_store(persist_dir)
        logger_inst.info(f"强制重建向量库，删除旧索引: {persist_dir}")
        vs = rebuild_vector_store(persist_dir, rules_dir, embeddings)
    else:
        print("🔄 智能加载/构建向量库...")
        vs = get_or_create_vector_store(persist_dir, rules_dir, embeddings, force_rebuild=False)

    if vs is None:
        print("❌ 向量库构建失败，请查看日志排查问题")
        logger_inst.error("向量库构建失败")
        return False

    total_ts = time.time() - start_ts

    # 4. 输出统计
    try:
        vector_count = vs._collection.count()
        chunk_count = len(documents)
        avg_chunk_chars = total_chars / chunk_count if chunk_count else 0
    except Exception:
        vector_count = "未知"
        avg_chunk_chars = 0

    print("\n" + separator)
    print("✅ 索引构建完成!")
    print(separator)
    print(f"  📊 规则文件数:       {file_count}")
    print(f"  📊 向量/分块数:      {vector_count}")
    print(f"  📊 平均分块长度:     {avg_chunk_chars:.0f} 字符")
    print(f"  📂 向量存储路径:     {persist_dir}")
    print(f"  ⏱️  总耗时:          {total_ts:.2f} 秒")
    print(f"                {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    print(separator)

    logger_inst.info(
        f"索引构建完成: files={file_count}, vectors={vector_count}, "
        f"chars={total_chars}, total_ts={total_ts:.2f}s"
    )

    return True


def main():
    ap = argparse.ArgumentParser(
        description="ISSF 2026 规则文档 - 向量索引构建/重建工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 默认构建/加载索引
  python -m backend.app.ingest

  # 强制重建索引
  python -m backend.app.ingest --rebuild

  # 指定规则目录和向量库路径
  python -m backend.app.ingest --rules-dir ./data/rules --persist-dir ./data/vector_store
        """
    )
    ap.add_argument("--rules-dir", default=None, help="规则文档目录（默认: data/rules/）")
    ap.add_argument("--persist-dir", default=None, help="向量库持久化目录（默认: data/vector_store/）")
    ap.add_argument("--rebuild", action="store_true", help="强制删除并重建索引")
    ap.add_argument("--project-root", default=None, help="项目根目录（默认自动推导）")
    args = ap.parse_args()

    path_cfg = get_path_config(args.project_root)
    rules_dir = args.rules_dir or path_cfg.RULES_DIR
    persist_dir = args.persist_dir or path_cfg.VECTOR_STORE_DIR

    ok = run_ingest(
        rules_dir=rules_dir,
        persist_dir=persist_dir,
        force_rebuild=args.rebuild,
        show_progress=False,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
