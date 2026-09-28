"""
document_processor.py - 文档处理公共工具
统一文档切分、标签提取、同义词映射等逻辑，消除代码重复
"""

import os
from typing import List, Dict, Set, Tuple, Optional
from langchain_core.documents import Document
from langchain_community.document_loaders import DirectoryLoader, TextLoader

# ============================================================
# 同义词映射表（优先从外部 JSON 加载，回退到内置默认）
# ============================================================
SYNONYM_MAP: Dict[str, List[str]] = {}
NAME_TAG_RULES: List[Tuple[str, List[str]]] = []
KEYWORD_TAG_MAP: Dict[str, str] = {}


def _load_synonyms_from_file(path: str) -> Dict[str, List[str]]:
    """从 JSON 文件加载同义词表，返回 synonym_map，失败返回空字典"""
    try:
        if not os.path.exists(path):
            return {}
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        # 规整化：确保值为 list
        result = {}
        for k, v in data.items():
            if isinstance(v, list):
                result[str(k)] = [str(x) for x in v]
            else:
                result[str(k)] = [str(v)]
        return result
    except Exception:
        return {}


# 默认内置同义词（当外部 JSON 不存在或缺省字段时使用）
_DEFAULT_SYNONYM_MAP: Dict[str, List[str]] = {
    # 故障/射击术语
    "臭子": ["哑弹", "哑火", "瞎火", "不发火", "misfire"],
    "哑弹": ["臭子", "哑火", "瞎火", "不发火", "misfire"],
    "瞎火": ["臭子", "哑弹", "哑火", "不发火", "misfire"],
    "卡壳": ["故障", "卡弹", "malfunction"],
    "空枪": ["干火", "dry fire", "dry_fire"],
    "干火": ["空枪", "dry fire", "dry_fire"],
    "允许故障": ["allowable malfunction", "allowable_malfunction", "malfunction"],
    "抢起枪": ["抢答", "early shot", "premature shot"],
    # 比赛/规则术语
    "加赛": ["附加赛", "shootoff", "shoot-off", "tie_break"],
    "附加赛": ["加赛", "shootoff", "shoot-off", "tie_break"],
    "同分": ["平局", "tie", "draw"],
    "决赛": ["final", "finals"],
    "资格赛": ["qualification", "preliminary"],
    "基础射击": ["base", "basic", "foundation"],
    "淘汰阶段": ["elimination", "knockout"],
    # 项目/类型
    "混合团体": ["mixed team", "mixed_team", "team event"],
    "团体决赛": ["team final", "team finals"],
    "三姿": ["3 positions", "3_positions", "three positions", "3-position"],
    "三姿决赛": ["3 positions final", "3_positions_final", "three positions final"],
    "立姿": ["standing", "standing position"],
    "跪姿": ["kneeling", "kneeling position"],
    "卧姿": ["prone", "prone position"],
    "个人": ["individual", "solo"],
    "步枪": ["rifle"],
    "手枪": ["pistol"],
    "飞碟": ["shotgun", "clay target"],
    "多向": ["trap"],
    "双向": ["skeet", "double skeet"],
    "速射": ["rapid fire", "rapid_fire"],
    "气步枪": ["air rifle", "air_rifle"],
    "气手枪": ["air pistol", "air_pistol"],
    # 装备/安全
    "装备检查": ["equipment control", "equipment_check", "EC"],
    "验枪": ["装备检查", "equipment control", "equipment_check", "EC"],
    "安全旗": ["安全棒", "安全插销", "安全指示器", "安全装置", "safety flag", "safety rod", "safety plug", "safety indicator", "ECI"],
    "安全棒": ["安全旗", "安全插销", "safety flag", "safety rod"],
    "安全插销": ["安全旗", "安全棒", "safety flag", "safety plug"],
    "枪口": ["muzzle", "barrel"],
    "上弹": ["装弹", "装填", "load", "loading"],
    "装包": ["装箱", "打包", "pack", "package"],
    # 判罚/计分
    "DSQ": ["取消资格", "disqualification", "disqualified"],
    "挑战": ["challenge", "VAR挑战", "video challenge"],
    "视频裁判": ["VAR", "video referee", "video_referee"],
    "抗议": ["申诉", "protest", "appeal"],
    "报到": ["check-in", "checkin", "reporting"],
    "时限": ["timeout", "time limit", "deadline"],
    "弹药": ["ammunition", "cartridge", "ammo"],
    "握把": ["grip", "pistol grip"],
    "脱靶": ["未中", "miss", "lost"],
    "中靶": ["命中", "hit"],
    "口头警告": ["verbal warning", "oral warning", "warning"],
    # 装备规格
    "纽扣": ["button", "fastener"],
    "按扣": ["snap", "snap fastener"],
    "拉链": ["zipper", "zip"],
    "魔术贴": ["velcro", "hook and loop"],
    "内层": ["inner layer", "undergarment", "underwear"],
    # 射击相关
    "精准": ["precision", "accurate"],
    "精准阶段": ["precision stage", "precise stage"],
    "速射阶段": ["rapid stage", "rapid-fire stage"],
    "灯光": ["light", "lighting"],
    "轮转": ["rotation", "cycle"],
}

_DEFAULT_NAME_TAG_RULES: List[Tuple[str, List[str]]] = [
    ("rifle", ["步枪", "rifle"]),
    ("pistol", ["手枪", "pistol"]),
    ("shotgun", ["飞碟", "霰弹", "shotgun"]),
    ("trap", ["多向", "trap"]),
    ("skeet", ["双向", "skeet"]),
    ("mixed", ["混合团体", "mixed_team"]),
    ("individual", ["个人", "individual"]),
    ("final", ["决赛", "final"]),
    ("qualification", ["资格赛", "qualification"]),
    ("apparel", ["服装", "装备"]),
    ("clothing", ["服装", "装备"]),
    ("ammunition", ["弹药"]),
    ("cartridge", ["弹药"]),
    ("protest", ["抗议", "申诉"]),
    ("appeal", ["抗议", "申诉"]),
    ("var", ["视频裁判", "VAR"]),
    ("technical", ["视频裁判", "VAR"]),
    ("malfunction", ["故障", "允许故障"]),
    ("dry_fir", ["空枪", "干火"]),
    ("tie", ["同分", "加赛"]),
    ("timeout", ["时限", "报到"]),
    ("grip", ["握把"]),
]

_DEFAULT_KEYWORD_TAG_MAP: Dict[str, str] = {
    "速射": "rapid_fire", "rapid fire": "rapid_fire",
    "气步枪": "air_rifle", "air rifle": "air_rifle",
    "气手枪": "air_pistol", "air pistol": "air_pistol",
    "三姿": "3_positions", "3 positions": "3_positions",
    "步枪": "rifle", "手枪": "pistol", "飞碟": "shotgun",
    "混合团体": "mixed_team", "个人": "individual",
    "决赛": "final", "资格赛": "qualification",
    "装备检查": "equipment_control", "空枪": "dry_fire", "干火": "dry_fire",
    "臭子": "misfire", "哑弹": "misfire", "哑火": "misfire",
    "卡壳": "malfunction", "故障": "malfunction", "允许故障": "allowable_malfunction",
    "同分": "tie", "加赛": "shootoff", "附加赛": "shootoff",
    "挑战": "challenge", "VAR": "video_referee", "视频裁判": "video_referee",
    "抗议": "protest", "申诉": "protest",
    "时限": "timeout", "报到": "checkin",
    "DSQ": "disqualification", "取消资格": "disqualification",
}


def init_synonyms_from_project(project_root: str = None, override: bool = False):
    """
    从项目默认路径加载同义词表：
      project_root/data/rules/synonyms.json
    若不存在则保留内置默认值；若 override=True，则外部文件为空字典也会覆盖内置字典为空。
    """
    global SYNONYM_MAP, NAME_TAG_RULES, KEYWORD_TAG_MAP
    if SYNONYM_MAP and not override:
        return
    path = None
    if project_root:
        path = os.path.join(project_root, "data", "rules", "synonyms.json")
    if not path or not os.path.exists(path):
        # 尝试相对于当前文件所在的项目根目录
        here = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.join(here, "..", "..", "data", "rules", "synonyms.json")
        candidate = os.path.abspath(candidate)
        if os.path.exists(candidate):
            path = candidate
    ext = _load_synonyms_from_file(path) if path else {}
    if not ext and not override:
        # 使用默认
        SYNONYM_MAP = _DEFAULT_SYNONYM_MAP
        NAME_TAG_RULES = list(_DEFAULT_NAME_TAG_RULES)
        KEYWORD_TAG_MAP = dict(_DEFAULT_KEYWORD_TAG_MAP)
    else:
        SYNONYM_MAP = ext if ext else {}
        # name_rules / keyword_map 也可外置，这里为简化先保持默认，仅替换主 synonym_map
        NAME_TAG_RULES = list(_DEFAULT_NAME_TAG_RULES)
        KEYWORD_TAG_MAP = dict(_DEFAULT_KEYWORD_TAG_MAP)


# 自动初始化（保持向后兼容）：优先外部文件，缺失则用默认值
init_synonyms_from_project()

# ============================================================
# 文档加载
# ============================================================
def load_markdown_documents(rules_dir: str) -> List[Document]:
    """
    从指定目录加载所有 Markdown 文档（支持多层嵌套子目录递归扫描）
    Args:
        rules_dir: 规则文档目录
    Returns:
        Document 列表（已附加 source_file/file_name/relative_path/yaml_metadata 元数据）
    """
    if not os.path.exists(rules_dir):
        raise FileNotFoundError(f"规则目录不存在: {rules_dir}")

    loader = DirectoryLoader(
        path=rules_dir,
        glob="**/*.md",                    # ✅ 递归匹配所有子目录下的 .md
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=False,
        recursive=True                     # ✅ 显式开启递归，兼容新旧版本 DirectoryLoader
    )
    documents = loader.load()

    # 附加统一的元数据
    for doc in documents:
        source_path = doc.metadata.get("source", "")
        source_file = os.path.basename(source_path)
        doc.metadata["source_file"] = source_file
        doc.metadata["file_name"] = source_file
        # 记录相对 rules_dir 的路径，方便判断归属哪个章节（如：06.通用规则/6.2_安全/xxx.md）
        try:
            if source_path:
                doc.metadata["relative_path"] = os.path.relpath(source_path, rules_dir)
            else:
                doc.metadata["relative_path"] = source_file
        except ValueError:
            doc.metadata["relative_path"] = source_file

        # 解析 YAML frontmatter（若存在）
        text = doc.page_content or ""
        if has_yaml_frontmatter(text):
            try:
                from .yaml_metadata_parser import parse_markdown_yaml
                meta = parse_markdown_yaml(text, source_file=source_file)
                if meta:
                    doc.metadata.setdefault("yaml_metadata", {})
                    doc.metadata["yaml_metadata"].update(meta)
                    for k in ("rule_version", "rule_category", "rule_article", "rule_clause", "rule_id"):
                        if k in meta and k not in doc.metadata:
                            doc.metadata[k] = str(meta[k])
            except Exception as e:
                # 不阻断主流程
                pass

    if not documents:
        raise FileNotFoundError(
            f"在 {rules_dir} 下（含所有子目录）没有找到任何 .md 规则文件，请检查目录结构。"
        )

    return documents

# ============================================================
# 智能文档切分
# ============================================================
def smart_split_documents(documents: List[Document]) -> List[Document]:
    """
    智能文档切分算法（统一版本）
    支持 Markdown 标题和中文序号两种切分策略
    Args:
        documents: 原始文档列表
    Returns:
        切分后的 Document 列表（含完整元数据）
    """
    all_chunks: List[Document] = []
    md_separators = ["\n## ", "\n### "]
    table_separators = ["\n一、", "\n二、", "\n三、", "\n四、", "\n五、"]

    for doc in documents:
        content = doc.page_content
        source_file = doc.metadata.get("source_file", "")
        file_name = doc.metadata.get("file_name", source_file) or source_file
        if not source_file:
            source_file = os.path.basename(doc.metadata.get("source", ""))
            file_name = source_file

        is_table_format = content.startswith("id\ttitle") or "id\ttitle\tcategory" in content[:100]

        if is_table_format:
            parts = None
            for sep in table_separators:
                if sep in content:
                    parts = content.split(sep)
                    break
            if not parts:
                parts = [content]

            for i, part in enumerate(parts):
                part = part.strip()
                if not part or len(part) < 10:
                    continue
                if 0 < i < len(table_separators):
                    part = table_separators[i - 1] + part
                if len(part) > 20:
                    chunk_doc = Document(
                        page_content=part,
                        metadata={
                            "source_file": source_file,
                            "file_name": file_name,
                            "chunk_id": len(all_chunks)
                        }
                    )
                    chunk_doc.metadata["doc_tags"] = extract_doc_tags(file_name, part)
                    # 继承 YAML 元数据
                    if "yaml_metadata" in doc.metadata:
                        chunk_doc.metadata["yaml_metadata"] = dict(doc.metadata["yaml_metadata"])
                    for k in ("rule_version", "rule_category", "rule_article", "rule_clause", "rule_id"):
                        if k in doc.metadata:
                            chunk_doc.metadata[k] = doc.metadata[k]
                    all_chunks.append(chunk_doc)
        else:
            parts = None
            for sep in md_separators:
                if sep in content:
                    parts = content.split(sep)
                    break
            if not parts:
                parts = [content]

            for i, part in enumerate(parts):
                part = part.strip()
                if not part or len(part) < 10:
                    continue
                if 0 < i < len(md_separators):
                    part = md_separators[i - 1] + part
                if len(part) > 20:
                    chunk_doc = Document(
                        page_content=part,
                        metadata={
                            "source_file": source_file,
                            "file_name": file_name,
                            "chunk_id": len(all_chunks)
                        }
                    )
                    chunk_doc.metadata["doc_tags"] = extract_doc_tags(file_name, part)
                    if "yaml_metadata" in doc.metadata:
                        chunk_doc.metadata["yaml_metadata"] = dict(doc.metadata["yaml_metadata"])
                    for k in ("rule_version", "rule_category", "rule_article", "rule_clause", "rule_id"):
                        if k in doc.metadata:
                            chunk_doc.metadata[k] = doc.metadata[k]
                    all_chunks.append(chunk_doc)

    return all_chunks


# ============================================================
# 文档标签提取
# ============================================================
def extract_doc_tags(file_name: str, content: str) -> str:
    """
    根据文件名和内容提取文档标签，用于增强检索
    Args:
        file_name: 文件名
        content: 文档内容
    Returns:
        逗号分隔的标签字符串
    """
    tags: Set[str] = set()
    name_lower = file_name.lower()

    for keyword, tag_list in NAME_TAG_RULES:
        if keyword in name_lower:
            tags.update(tag_list)

    content_lower = content.lower()
    for kw, tag in KEYWORD_TAG_MAP.items():
        if kw.lower() in content_lower:
            tags.add(tag)

    return ",".join(tags) if tags else "general"


# ============================================================
# 查询同义词扩展
# ============================================================
def expand_query_synonyms(query: str, max_expanded_terms: int = 5) -> str:
    """
    扩展查询同义词，提升召回率
    Args:
        query: 原始查询
        max_expanded_terms: 最大扩展词数量
    Returns:
        扩展后的查询字符串
    """
    expanded_terms: Set[str] = set()
    for key, synonyms in SYNONYM_MAP.items():
        if key in query:
            expanded_terms.add(key)
            expanded_terms.update(synonyms)
    if expanded_terms:
        expanded_part = " ".join(list(expanded_terms)[:max_expanded_terms])
        return f"{query} {expanded_part}"
    return query


# ============================================================
# YAML frontmatter 小工具（避免循环导入）
# ============================================================
def has_yaml_frontmatter(text: str) -> bool:
    if not text or not text.startswith("---"):
        return False
    idx = text.find("\n", 3)
    if idx == -1:
        return False
    second = text.find("---", idx)
    return second > 0
# ============================================================
# 长文档章节拆分（P2-3：上传文档按标题拆分为多条规则）
# ============================================================
def split_markdown_by_headings(text: str, max_chunk_chars: int = 8000) -> list[dict]:
    """
    按 Markdown 标题（#、##、###）将长文档拆分为多个章节
    Args:
        text: Markdown 原始文本
        max_chunk_chars: 单个章节最大字符数，超过将继续拆分
    Returns:
        [{"heading": "标题文本", "level": 1, "content": "章节内容"}, ...]
    """
    import re
    if not text or not text.strip():
        return []
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    matches = list(heading_pattern.finditer(text))
    if not matches:
        return [{"heading": "", "level": 0, "content": text.strip()}]
    sections: list[dict] = []
    for i, m in enumerate(matches):
        heading_text = m.group(2).strip()
        level = len(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append({"heading": heading_text, "level": level, "content": content})
    return _split_oversized(sections, max_chunk_chars)

def _to_raw_sections(text: str, source_file: str = "") -> list[dict]:
    """
    将 Markdown 文本拆分为原始章节列表（保留标题路径）
    Returns:
        [{"heading_path": "1. 概述 > 1.1 定义", "content": "..."}, ...]
    """
    if not text or not text.strip():
        return [{"heading_path": os.path.splitext(source_file)[0] if source_file else "未命名",
                 "content": (text or "").strip()}]
    sections = split_markdown_by_headings(text)
    if not sections:
        return [{"heading_path": os.path.splitext(source_file)[0] if source_file else "未命名",
                 "content": (text or "").strip()}]
    result: list[dict] = []
    heading_stack: list[str] = []
    for sec in sections:
        level = sec["level"]
        heading = sec["heading"]
        while len(heading_stack) >= level:
            heading_stack.pop()
        heading_stack.append(heading)
        path = " > ".join(heading_stack)
        result.append({"heading_path": path, "content": sec["content"]})
    return result

def _split_oversized(sections: list[dict], max_chars: int = 8000) -> list[dict]:
    """对超大章节按段落二次拆分"""
    import re
    result: list[dict] = []
    for sec in sections:
        if len(sec["content"]) <= max_chars:
            result.append(sec)
            continue
        paragraphs = re.split(r"\n{2,}", sec["content"])
        current = ""
        for para in paragraphs:
            if len(current) + len(para) > max_chars and current:
                result.append({"heading": sec["heading"], "level": sec["level"],
                               "content": current.strip()})
                current = para
            else:
                current = (current + "\n\n" + para).strip()
        if current:
            result.append({"heading": sec["heading"], "level": sec["level"],
                           "content": current.strip()})
    return result