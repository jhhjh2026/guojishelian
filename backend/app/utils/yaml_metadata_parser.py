"""
yaml_metadata_parser.py - Markdown YAML 前置元数据解析工具
支持解析 Markdown 文档顶部的 YAML frontmatter，提取规则版本、类别、条款号等元数据，
增强检索与过滤能力，且不破坏现有非 YAML 文档兼容性。
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document


def has_yaml_frontmatter(text: str) -> bool:
    """检测文本是否以 YAML frontmatter（--- ... ---）开头"""
    if not text or not text.startswith("---"):
        return False
    # 再检查紧跟着的是否有第二个 ---
    idx = text.find("\n", 3)
    if idx == -1:
        return False
    second = text.find("---", idx)
    return second > 0


def _parse_yaml_block(yaml_text: str) -> Dict[str, Any]:
    """
    简易 YAML 解析器，支持常见键值对与列表
    尽量兼容简单 YAML，首选用标准 yaml 库，失败时回退到简易逐行解析
    """
    if not yaml_text:
        return {}
    # 尝试使用标准库
    try:
        import yaml  # noqa: F401 (optional dependency)

        loaded = yaml.safe_load(yaml_text)
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        pass

    # 回退：简易键值解析（不处理嵌套结构，但覆盖大部分需求）
    result: Dict[str, Any] = {}
    for line in yaml_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        # 去掉可能的引号
        if len(value) >= 2 and ((value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'"))):
            value = value[1:-1]
        # 列表值：以 "- " 开头
        if value.startswith("- "):
            # 简单处理：把剩余以 "- " 开头的行也作为列表项
            items = [value[2:].strip()]
            # 同一行后续可能还有：如 "a: - x\n  - y" 不常见，暂不复杂处理
            result[key] = items
            continue
        result[key] = value
    return result


def parse_markdown_yaml(text: str, source_file: str = "") -> Dict[str, Any]:
    """
    从 Markdown 文本中解析 YAML frontmatter，返回元数据字典
    """
    if not has_yaml_frontmatter(text):
        return {}
    idx2 = text.find("---", 3)
    if idx2 == -1:
        return {}
    # 第二个 --- 可能在同一行
    second_line_idx = text.find("\n", 3)
    if second_line_idx != -1 and idx2 > second_line_idx:
        # 正常情况：第2个---在下一行
        yaml_text = text[3:idx2].strip()
        body = text[idx2 + 3 :].lstrip("\n")
    else:
        # 同一行：--- key: val ---，则中间部分为 yaml_text
        yaml_text = text[3:idx2].strip()
        body = text[idx2 + 3 :].lstrip("\n")

    meta = _parse_yaml_block(yaml_text)
    # 附加到元数据
    meta["_source_file"] = source_file
    meta["_has_yaml"] = True
    return meta


def extract_yaml_metadata(
    documents: List[Document],
    apply_to_content: bool = True,
) -> List[Document]:
    """
    批量从 Document 列表中解析 YAML frontmatter，并将元数据写入 document.metadata
    键约定：
      - 规则元数据直接写入 metadata
      - 若存在 rule_id / article / clause 字段，会额外生成可检索字段
      - 正文前端移除 frontmatter（可选）
    """
    parsed: List[Document] = []
    for doc in documents:
        text = doc.page_content or ""
        source = doc.metadata.get("source_file") or doc.metadata.get("source", "") or ""
        meta = parse_markdown_yaml(text, source_file=source)
        if meta:
            # 合并到现有 metadata，避免覆盖
            new_meta = dict(doc.metadata)
            new_meta.setdefault("yaml_metadata", {})
            new_meta["yaml_metadata"].update(meta)
            # 常见字段平铺：便于后续检索过滤
            if "version" in meta:
                new_meta.setdefault("rule_version", meta["version"])
            if "category" in meta:
                new_meta.setdefault("rule_category", meta["category"])
            if "article" in meta:
                new_meta.setdefault("rule_article", str(meta["article"]))
            if "clause" in meta:
                new_meta.setdefault("rule_clause", str(meta["clause"]))
            if "rule_id" in meta:
                new_meta.setdefault("rule_id", str(meta["rule_id"]))

            if apply_to_content:
                # 去除 frontmatter 避免干扰检索
                idx = text.find("---", 3)
                if idx != -1:
                    text = text[idx + 3 :].lstrip("\n")
                doc = Document(page_content=text, metadata=new_meta)
        parsed.append(doc)
    return parsed


__all__ = [
    "has_yaml_frontmatter",
    "parse_markdown_yaml",
    "extract_yaml_metadata",
]
