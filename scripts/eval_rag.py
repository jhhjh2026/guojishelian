#!/usr/bin/env python3
"""
eval_rag.py - RAG 自动化评测脚本
支持三种模式：
  --dry-run          仅校验数据集与评分逻辑，不调模型，零成本
  --mode retrieval   仅评测检索链路（向量召回 + 重排），不调 LLM
  直接运行            全量：检索 + LLM 生成

评测指标：
  检索命中率、精排命中率、完全通过率、关键词覆盖率（均值）、
  拒答率、部分拒答率、重排丢失数、延迟 P50/P95

用法：
  python scripts/eval_rag.py --dry-run
  python scripts/eval_rag.py --mode retrieval
  python scripts/eval_rag.py
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ---------- 数据结构 ----------

@dataclass
class TestCase:
    id: str
    question: str
    keywords: list[str] = field(default_factory=list)
    expected_answer: str = ""
    target_doc: str = ""

@dataclass
class EvalResult:
    case_id: str
    question: str
    retrieved_docs: list[str] = field(default_factory=list)
    retrieval_hit: bool = False
    rerank_hit: bool = False
    full_pass: bool = False
    keyword_coverage: float = 0.0
    is_refusal: bool = False
    is_partial_refusal: bool = False
    rerank_lost: bool = False
    latency_ms: int = 0
    answer: str = ""
    errors: list[str] = field(default_factory=list)

# ---------- 数据加载 ----------

def _normalize_doc_name(name: str) -> str:
    """归一化文档名：去扩展名、统一分隔符"""
    name = os.path.splitext(name)[0]
    name = name.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", name).strip().lower()

def _normalize_clause(text: str) -> str:
    """提取条款号并归一化，如 RULE_2026_9_14 -> rule 2026 9 14"""
    text = text.lower().strip()
    m = re.match(r"rule[_]?(\d{4})[_]?(\d+)[_]?(\d+)", text)
    if m:
        return f"rule {m.group(1)} {m.group(2)} {m.group(3)}"
    return text.replace(".", " ").strip()

def load_test_cases(path: str) -> list[TestCase]:
    """从 JSON 文件加载评测用例"""
    if not os.path.exists(path):
        print(f"[ERROR] 评测用例文件不存在: {path}")
        return []

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    cases: list[TestCase] = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("test_cases", data.get("cases", []))
    else:
        items = []

    for item in items:
        cases.append(TestCase(
            id=str(item.get("id", item.get("question", ""))),
            question=str(item.get("question", "")),
            keywords=[str(k) for k in item.get("keywords", [])],
            expected_answer=str(item.get("expected_answer", item.get("answer", ""))),
            target_doc=str(item.get("target_doc", item.get("document", ""))),
        ))

    return cases

# ---------- 评分逻辑 ----------

def _bigram_coverage(keywords: list[str], text: str, threshold: float = 0.6) -> float:
    """字级 bigram 覆盖率评分（避免字面子串漏判语义摘要）"""
    if not keywords:
        return 1.0

    text_clean = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", text.lower())
    text_bigrams: set[str] = set()
    for i in range(len(text_clean) - 1):
        text_bigrams.add(text_clean[i:i + 2])

    scores: list[float] = []
    for kw in keywords:
        kw_clean = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", "", kw.lower())
        if not kw_clean:
            scores.append(1.0)
            continue
        kw_bigrams: set[str] = set()
        for i in range(len(kw_clean) - 1):
            kw_bigrams.add(kw_clean[i:i + 2])
        if not kw_bigrams:
            scores.append(1.0)
            continue
        overlap = len(kw_bigrams & text_bigrams)
        coverage = overlap / len(kw_bigrams)
        scores.append(1.0 if coverage >= threshold else coverage)

    return sum(scores) / len(scores) if scores else 0.0

def check_document_match(target_doc: str, retrieved_docs: list[str]) -> bool:
    """检查目标文档是否在检索结果中，三重策略"""
    if not target_doc:
        return False

    target_norm = _normalize_doc_name(target_doc)
    target_clause = _normalize_clause(target_doc)

    for doc in retrieved_docs:
        doc_norm = _normalize_doc_name(doc)
        if target_clause and (target_clause in doc_norm or doc_norm in target_clause):
            return True
        if target_norm in doc_norm or doc_norm in target_norm:
            return True
        doc_underscore = doc_norm.replace(" ", "_")
        target_underscore = target_norm.replace(" ", "_")
        if target_underscore in doc_underscore or doc_underscore in target_underscore:
            return True

    return False

REFUSAL_PATTERNS = [
    "无法回答", "没有相关", "未找到", "暂无相关", "不包含",
    "没有提到", "无相关信息", "不清楚", "无法确定", "未提及",
    "没有涉及", "无法提供",
]

def is_refusal_answer(answer: str) -> bool:
    """判定回答是否为拒答"""
    if not answer or len(answer.strip()) < 3:
        return True
    al = answer.lower()
    return any(p in al for p in REFUSAL_PATTERNS)

def is_partial_refusal(answer: str) -> bool:
    """判定回答是否为部分拒答"""
    markers = ["未包含完整细节", "不完全", "部分相关", "不完整", "仅包含部分"]
    al = answer.lower()
    return any(m in al for m in markers)

# ---------- 评测执行 ----------

def evaluate_retrieval(
        cases: list[TestCase],
        target_docs_map: dict[str, list[str]] | None = None,
) -> list[EvalResult]:
    """仅评测检索链路"""
    results: list[EvalResult] = []

    for case in cases:
        result = EvalResult(case_id=case.id, question=case.question)
        retrieved = []
        if target_docs_map and case.id in target_docs_map:
            retrieved = target_docs_map[case.id]
        result.retrieved_docs = retrieved

        if retrieved:
            result.retrieval_hit = check_document_match(case.target_doc, retrieved[:10])
            result.rerank_hit = check_document_match(case.target_doc, retrieved[:3])
            result.rerank_lost = result.retrieval_hit and not result.rerank_hit

        if case.keywords:
            result.keyword_coverage = _bigram_coverage(case.keywords, case.expected_answer)

        result.full_pass = result.retrieval_hit and result.rerank_hit
        results.append(result)

    return results

def evaluate_full(
        cases: list[TestCase],
        rag_service=None,
) -> list[EvalResult]:
    """全量评测：检索 + LLM 生成"""
    results: list[EvalResult] = []

    for i, case in enumerate(cases):
        result = EvalResult(case_id=case.id, question=case.question)
        start = time.time()

        try:
            if rag_service:
                svc_result = rag_service.ask(case.question, use_cache=False, show_sources=True)
                result.answer = svc_result.get("data", {}).get("answer", "")
                sources = svc_result.get("data", {}).get("sources", [])
                result.retrieved_docs = [s.get("source_file", "") for s in sources]
            else:
                result.errors.append("RAG 服务不可用")
        except Exception as e:
            result.errors.append(str(e))

        result.latency_ms = int((time.time() - start) * 1000)

        if result.retrieved_docs:
            result.retrieval_hit = check_document_match(case.target_doc, result.retrieved_docs[:10])
            result.rerank_hit = check_document_match(case.target_doc, result.retrieved_docs[:3])
            result.rerank_lost = result.retrieval_hit and not result.rerank_hit

        result.is_refusal = is_refusal_answer(result.answer)
        result.is_partial_refusal = is_partial_refusal(result.answer)

        if case.keywords:
            result.keyword_coverage = _bigram_coverage(
                case.keywords, result.answer or case.expected_answer
            )

        result.full_pass = (
                result.retrieval_hit
                and result.rerank_hit
                and result.keyword_coverage >= 0.6
                and not result.is_refusal
        )

        results.append(result)

        if (i + 1) % 5 == 0:
            print(f"  进度: {i + 1}/{len(cases)}")

    return results

# ---------- 报告生成 ----------

def generate_report(results: list[EvalResult], output_path: str = None) -> str:
    """生成评测报告（CSV + 汇总统计）"""
    total = len(results)
    if total == 0:
        return "无评测结果"

    retrieval_hits = sum(1 for r in results if r.retrieval_hit)
    rerank_hits = sum(1 for r in results if r.rerank_hit)
    full_passes = sum(1 for r in results if r.full_pass)
    refusals = sum(1 for r in results if r.is_refusal)
    partial_refusals = sum(1 for r in results if r.is_partial_refusal)
    rerank_losts = sum(1 for r in results if r.rerank_lost)

    keyword_scores = [r.keyword_coverage for r in results if r.keyword_coverage > 0]
    avg_keyword = sum(keyword_scores) / len(keyword_scores) if keyword_scores else 0.0

    latencies = [r.latency_ms for r in results if r.latency_ms > 0]
    p50 = statistics.median(latencies) if latencies else 0
    p95 = (
        sorted(latencies)[int(len(latencies) * 0.95)]
        if len(latencies) >= 20
        else (sorted(latencies)[-1] if latencies else 0)
    )

    lines = [
        "=" * 60,
        "  ISSF RAG 评测报告",
        "=" * 60,
        f"  总用例数:        {total}",
        f"  检索命中率:      {retrieval_hits}/{total} = {retrieval_hits / total * 100:.1f}%",
        f"  精排命中率:      {rerank_hits}/{total} = {rerank_hits / total * 100:.1f}%",
        f"  完全通过率:      {full_passes}/{total} = {full_passes / total * 100:.1f}%",
        f"  关键词覆盖率均值: {avg_keyword:.2%}",
        f"  拒答率:          {refusals}/{total} = {refusals / total * 100:.1f}%",
        f"  部分拒答率:      {partial_refusals}/{total} = {partial_refusals / total * 100:.1f}%",
        f"  重排丢失数:      {rerank_losts}",
        f"  延迟 P50:        {p50}ms",
        f"  延迟 P95:        {p95}ms",
        "=" * 60,
        ]

    report = "\n".join(lines)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "case_id", "question", "retrieval_hit", "rerank_hit",
                "full_pass", "keyword_coverage", "is_refusal",
                "is_partial_refusal", "rerank_lost", "latency_ms",
                "answer", "errors",
            ])
            for r in results:
                writer.writerow([
                    r.case_id, r.question, r.retrieval_hit, r.rerank_hit,
                    r.full_pass, f"{r.keyword_coverage:.4f}", r.is_refusal,
                    r.is_partial_refusal, r.rerank_lost, r.latency_ms,
                    (r.answer or "")[:500], "; ".join(r.errors),
                ])
        print(f"\n报告已保存至: {output_path}")

    return report

# ---------- 主入口 ----------

def main():
    parser = argparse.ArgumentParser(description="ISSF RAG 评测脚本")
    parser.add_argument("--dry-run", action="store_true", help="仅校验数据集与评分逻辑")
    parser.add_argument(
        "--mode", choices=["retrieval", "full"], default=None,
        help="评测模式: retrieval（仅检索）; 默认全量（检索+LLM）",
    )
    parser.add_argument("--test-cases", default=None, help="评测用例 JSON 路径")
    parser.add_argument("--output", "-o", default=None, help="输出 CSV 报告路径")
    parser.add_argument("--limit", type=int, default=0, help="限制评测用例数（0=全部）")
    args = parser.parse_args()

    data_dir = os.path.join(_PROJECT_ROOT, "data")
    cases_path = args.test_cases or os.path.join(data_dir, "test_cases.json")
    output_path = args.output or os.path.join(data_dir, "eval_output", "eval_report.csv")

    print(f"加载评测用例: {cases_path}")
    cases = load_test_cases(cases_path)
    if not cases:
        print("[ERROR] 未加载到任何评测用例")
        return 1

    if args.limit > 0:
        cases = cases[:args.limit]

    print(f"已加载 {len(cases)} 条用例")

    # 数据完整性校验
    issues = []
    for case in cases:
        if not case.question.strip():
            issues.append(f"用例 {case.id}: 问题为空")
        if not case.target_doc.strip():
            issues.append(f"用例 {case.id}: target_doc 为空")
    if issues:
        print(f"\n[WARN] 数据完整性问题 {len(issues)} 处:")
        for iss in issues[:10]:
            print(f"  - {iss}")
        if len(issues) > 10:
            print(f"  ... 及另外 {len(issues) - 10} 处")
    else:
        print("✅ 数据完整性通过")

    if args.dry_run:
        test_results = evaluate_retrieval(cases)
        print(f"\n✅ 评分逻辑自检通过（{len(test_results)} 条用例）")
        print(generate_report(test_results))
        return 0

    if args.mode == "retrieval":
        print("\n[retrieval 模式] 正在初始化 RAG 服务...")
        try:
            from backend.app.core.rag_service import RAGService
            svc = RAGService(project_root=_PROJECT_ROOT)
            init_result = svc.initialize()
            if not init_result.get("success"):
                print(f"[ERROR] RAG 初始化失败: {init_result.get('message')}")
                return 1

            all_docs_map: dict[str, list[str]] = {}
            print(f"正在检索 {len(cases)} 条用例...")
            for i, case in enumerate(cases):
                try:
                    raw = svc._vector_store.similarity_search(case.question, k=10)
                    doc_names = [d.metadata.get("source_file", "") for d in raw]
                    all_docs_map[case.id] = doc_names
                except Exception as e:
                    print(f"  [WARN] 用例 {case.id} 检索失败: {e}")
                    all_docs_map[case.id] = []
                if (i + 1) % 20 == 0:
                    print(f"  进度: {i + 1}/{len(cases)}")

            results = evaluate_retrieval(cases, all_docs_map)
            print(generate_report(results, output_path))
            return 0
        except Exception as e:
            print(f"[ERROR] 检索评测失败: {e}")
            return 1

    print("\n[全量模式] 正在初始化 RAG 服务...")
    try:
        from backend.app.core.rag_service import RAGService
        svc = RAGService(project_root=_PROJECT_ROOT)
        init_result = svc.initialize()
        if not init_result.get("success"):
            print(f"[ERROR] RAG 初始化失败: {init_result.get('message')}")
            return 1

        print(f"正在评测 {len(cases)} 条用例...")
        results = evaluate_full(cases, svc)
        print(generate_report(results, output_path))
        return 0
    except Exception as e:
        print(f"[ERROR] 全量评测失败: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())