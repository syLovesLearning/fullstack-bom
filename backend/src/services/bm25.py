"""中英混排 BM25 检索与 RRF 倒数排名融合算法。"""

import math
import re
from typing import Any

_ZH_STOPWORDS = {
    "的", "了", "与", "和", "是", "在", "有", "为", "以", "及", "或", "对",
    "中", "上", "下", "这", "那", "它", "你", "我", "他", "吗", "呢", "吧",
    "啊", "如", "何", "怎", "么", "什", "请", "问", "把", "被", "让", "从",
}
_EN_STOPWORDS = {
    "the", "a", "an", "is", "are", "in", "on", "of", "to", "and", "or", "for", "with",
}


def tokenize(text: str) -> list[str]:
    """英文过滤停用词；中文过滤停用词后优先保留双字切片，消除单字噪声。"""
    tokens: list[str] = []
    for part in re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+", text.lower()):
        if part.isascii():
            if part not in _EN_STOPWORDS and len(part) > 1:
                tokens.append(part)
        else:
            cleaned = "".join(ch for ch in part if ch not in _ZH_STOPWORDS)
            if not cleaned:
                continue
            if len(cleaned) == 1:
                tokens.append(cleaned)
            else:
                tokens.extend(cleaned[i : i + 2] for i in range(len(cleaned) - 1))
    return tokens


def bm25_rank(
    query: str, docs: list[dict[str, Any]], top_k: int = 15, k1: float = 1.5, b: float = 0.75
) -> list[dict[str, Any]]:
    if not docs:
        return []
    q_tokens = tokenize(query)
    if not q_tokens:
        return []

    tokenized_docs = [tokenize(f"{d.get('heading_path', '')} {d['content']}") for d in docs]
    avgdl = sum(len(t) for t in tokenized_docs) / len(tokenized_docs)
    n_docs = len(docs)

    df: dict[str, int] = {}
    for t_list in tokenized_docs:
        for term in set(t_list):
            df[term] = df.get(term, 0) + 1

    scored: list[tuple[float, dict[str, Any]]] = []
    for doc, t_list in zip(docs, tokenized_docs):
        dl = len(t_list)
        if dl == 0:
            continue
        tf: dict[str, int] = {}
        for term in t_list:
            tf[term] = tf.get(term, 0) + 1
        score = 0.0
        for q in q_tokens:
            if q not in tf:
                continue
            idf = math.log((n_docs - df[q] + 0.5) / (df[q] + 0.5) + 1.0)
            freq = tf[q]
            denom = freq + k1 * (1 - b + b * dl / avgdl)
            score += idf * (freq * (k1 + 1)) / denom
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:top_k]]


def rrf_fuse(
    vec_hits: list[dict[str, Any]], bm25_hits: list[dict[str, Any]], k: int = 60
) -> list[dict[str, Any]]:
    """倒数排名融合 (Reciprocal Rank Fusion)。"""
    scores: dict[int, float] = {}
    by_id: dict[int, dict[str, Any]] = {}

    for rank, item in enumerate(vec_hits, start=1):
        cid = int(item["id"])
        by_id[cid] = item
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)

    for rank, item in enumerate(bm25_hits, start=1):
        cid = int(item["id"])
        by_id.setdefault(cid, item)
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)

    ordered_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return [by_id[cid] for cid in ordered_ids]
