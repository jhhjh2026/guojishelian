"""
vector_store_manager.py - 向量库管理工具
统一向量库加载、重建、删除逻辑，消除代码重复并保证一致性
"""

import os
import shutil
import json
import logging
from typing import Optional, List
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from .document_processor import load_markdown_documents, smart_split_documents

logger = logging.getLogger("vector_store_store_manager")


def _sanitize_metadata(metadata: dict) -> dict:
    """Make metadata safe for Chroma by converting unsupported values to strings."""
    if not isinstance(metadata, dict):
        return {}
    safe = {}
    for key, value in metadata.items():
        if value is None or isinstance(value, (str, int, float, bool)):
            safe[key] = value
        elif isinstance(value, dict):
            try:
                safe[key] = json.dumps(value, ensure_ascii=False)
            except Exception:
                safe[key] = str
        elif isinstance(value, list):
            safe[key] = [str(v) for v in value]
        else:
            safe[key] = str(value)
    return safe


def delete_vector_store(persist_directory: str) -> None:
    """删除旧的向量存储目录"""
    if os.path.exists(persist_directory):
        try:
            shutil.rmtree(persist_directory)
            logger.info(f"已删除旧向量存储: {persist_directory}")
        except Exception as e:
            logger.warning(f"删除旧向量存储失败: {e}")

def _get_rules_files(rules_dir: str) -> Optional[List[tuple]]:
    """
    获取规则文件列表及其修改时间: [(abs_path, mtime, 相对路径文件名), ...]
    支持多层嵌套子目录（如 01.ISSF章程/1.1_xxx/规则.md），兼容 2026 新规则的目录组织方式。
    """
    if not os.path.exists(rules_dir):
        return None
    files = []
    for root, _dirs, file_names in os.walk(rules_dir):
        for f in file_names:
            if f.lower().endswith('.md'):
                abs_path = os.path.join(root, f)
                # 用相对 rules_dir 的路径作为显示名，便于定位文件在哪个子目录
                rel_path = os.path.relpath(abs_path, rules_dir)
                try:
                    mtime = os.path.getmtime(abs_path)
                except OSError:
                    mtime = 0.0
                files.append((abs_path, mtime, rel_path))
    return sorted(files, key=lambda x: x[2])

def rebuild_vector_store(
        persist_directory: str,
        rules_dir: str,
        embeddings: Embeddings
) -> Optional[Chroma]:
    """强制重建向量存储：读取文档 -> 切分 -> 向量化 -> 持久化"""
    try:
        os.makedirs(persist_directory, exist_ok=True)

        logger.info(f"从 {rules_dir} 加载文档...")
        documents = load_markdown_documents(rules_dir)
        if not documents:
            logger.error("没有加载到任何规则文档")
            return None

        logger.info("执行智能文档切分...")
        chunks = smart_split_documents(documents)
        if not chunks:
            logger.error("文档切分后没有得到有效 chunk")
            return None

        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_id"] = i
            if "doc_tags" not in chunk.metadata:
                chunk.metadata["doc_tags"] = "general"
            chunk.metadata = _sanitize_metadata(chunk.metadata)

        logger.info(f"开始向量化 {len(chunks)} 个 chunks...")
        vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=persist_directory
        )

        logger.info(f"向量存储重建完成，共 {len(chunks)} 个 chunk")
        return vector_store

    except Exception as e:
        logger.error(f"重建向量存储失败: {e}", exc_info=True)
        return None

def get_or_create_vector_store(
        persist_directory: str,
        rules_dir: str,
        embeddings: Embeddings,
        force_rebuild: bool = False
) -> Optional[Chroma]:
    """
    智能获取或创建向量存储：
      - force_rebuild=True → 强制重建
      - 目录不存在 → 重建
      - 向量数量异常 → 重建
      - 否则 → 直接加载
    """
    if force_rebuild:
        logger.info("force_rebuild=True，强制重建向量库...")
        delete_vector_store(persist_directory)
        return rebuild_vector_store(persist_directory, rules_dir, embeddings)

    files = _get_rules_files(rules_dir)
    if not files:
        logger.error(f"没有在 {rules_dir} 找到任何规则文件")
        return None

    if not os.path.exists(persist_directory):
        logger.info("向量存储目录不存在，开始构建...")
        return rebuild_vector_store(persist_directory, rules_dir, embeddings)

    try:
        vs = Chroma(
            persist_directory=persist_directory,
            embedding_function=embeddings
        )
        vector_count = vs._collection.count()
        file_count = len(files)

        if vector_count < file_count or vector_count == 0:
            logger.info(
                f"向量数量({vector_count})与文件数量({file_count})不匹配，重建向量存储..."
            )
            delete_vector_store(persist_directory)
            return rebuild_vector_store(persist_directory, rules_dir, embeddings)

        logger.info(f"成功加载已存在向量库，共 {vector_count} 个向量")
        return vs

    except Exception as e:
        logger.warning(f"加载现有向量库失败 ({e})，将进行重建...")
        delete_vector_store(persist_directory)
        return rebuild_vector_store(persist_directory, rules_dir, embeddings)