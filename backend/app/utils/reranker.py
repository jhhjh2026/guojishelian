"""
reranker.py - 重排模型工具
封装 DashScope gte-rerank-v2 重排接口，对向量库粗召回的文档进行二次精排，
提升检索精度和答案质量。
"""

import logging
import time
from typing import List
from langchain_core.documents import Document

logger = logging.getLogger("reranker")

def rerank_documents(
        query: str,
        documents: List[Document],
        api_key: str,
        model: str = "gte-rerank-v2",
        top_n: int = 3,
        return_documents: bool = True,
        max_retries: int = 3,
        retry_delay: float = 1.0,
) -> List[Document]:
    """
    使用 DashScope gte-rerank-v2 模型对粗召回文档进行重排，
    按相关性得分从高到低排序后返回 top_n 个最相关的文档。

    Args:
        query: 用户查询/问题
        documents: 向量库粗召回的 Document 列表
        api_key: DashScope API Key
        model: 重排模型名称，默认 gte-rerank-v2
        top_n: 重排后保留的文档数量
        return_documents: 是否返回带得分的文档（DashScope 参数）
        max_retries: 接口调用失败时的重试次数
        retry_delay: 重试间隔（秒），指数退避

    Returns:
        重排后的 Document 列表（已按相关性降序排序，截断到 top_n）
        如果重排失败则返回原 documents 的前 top_n 个，保证链路不中断
    """
    if not documents:
        logger.warning("重排输入文档为空，直接返回空列表")
        return []

    if top_n <= 0:
        top_n = len(documents)

    if len(documents) <= top_n:
        logger.info(f"召回文档数({len(documents)}) <= top_n({top_n})，跳过重排")
        return documents[:top_n]

    try:
        import dashscope
    except ImportError:
        logger.error("dashscope 未安装，无法使用重排功能，回退到原排序")
        return documents[:top_n]

    if not api_key:
        logger.warning("DASHSCOPE_API_KEY 为空，跳过重排，回退到原排序")
        return documents[:top_n]

    dashscope.api_key = api_key

    docs_contents: List[str] = []
    for doc in documents:
        content = doc.page_content or ""
        if len(content) > 3000:
            content = content[:3000]
        docs_contents.append(content)

    try:
        rerank_class = dashscope.TextReRank
    except AttributeError:
        rerank_class = dashscope.TextRanking

    delay = retry_delay

    for attempt in range(max_retries + 1):
        try:
            logger.info(
                f"[重排 {attempt + 1}/{max_retries}] 调用 {model}: query={query[:30]}... "
                f"docs={len(documents)} -> top_n={top_n}"
            )
            resp = rerank_class.call(
                model=model,
                query=query,
                documents=docs_contents,
                top_n=min(top_n, len(docs_contents)),
                return_documents=return_documents,
            )

            if resp is None:
                raise RuntimeError("重排接口返回 None")

            output = getattr(resp, "output", None) or {}
            results = output.get("results", []) if isinstance(output, dict) else []

            if not results:
                raise RuntimeError(f"重排接口 results 为空，resp={resp}")

            reranked_docs: List[Document] = []
            seen_indices = set()

            for item in results:
                idx = item.get("index")
                score = item.get("relevance_score") or item.get("score", 0.0)

                if idx is None or idx < 0 or idx >= len(documents):
                    continue
                if idx in seen_indices:
                    continue
                seen_indices.add(idx)

                original_doc = documents[idx]
                new_metadata = dict(original_doc.metadata)
                new_metadata["rerank_score"] = score
                new_metadata["rerank_model"] = model
                reranked_docs.append(
                    Document(
                        page_content=original_doc.page_content,
                        metadata=new_metadata,
                    )
                )

                if len(reranked_docs) >= top_n:
                    break

            if len(reranked_docs) < top_n:
                for i, doc in enumerate(documents):
                    if i not in seen_indices:
                        new_metadata = dict(doc.metadata)
                        new_metadata["rerank_score"] = 0.0
                        new_metadata["rerank_model"] = model
                        reranked_docs.append(
                            Document(
                                page_content=doc.page_content,
                                metadata=new_metadata,
                            )
                        )
                        seen_indices.add(i)
                        if len(reranked_docs) >= top_n:
                            break

            logger.info(
                f"[重排完成] 共重排 {len(reranked_docs)} 个文档，"
                f"top3 得分: {[round(d.metadata.get('rerank_score', 0), 4) for d in reranked_docs[:3]]}"
            )
            return reranked_docs[:top_n]

        except Exception as e:
            if attempt < max_retries:
                logger.warning(
                    f"[重排重试 {attempt + 1}/{max_retries}] 调用失败: {e}, "
                    f"{delay:.1f}s 后重试..."
                )
                time.sleep(delay)
                delay *= 2.0
            else:
                logger.error(
                    f"[重排失败] 在 {max_retries + 1} 次尝试后仍失败: {e}，"
                    f"回退到原排序"
                )

    logger.warning("重排全部失败，回退到向量库原始排序")
    return documents[:top_n]