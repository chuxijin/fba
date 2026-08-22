from __future__ import annotations

import re

from hashlib import blake2b
from math import sqrt

VECTOR_DIM = 128
FEATURE_HASH_MODEL = 'feature-hash-v1'


def tokenize(text: str) -> list[str]:
    """生成适合中文申论短文本的字、二元词和三元词。"""
    tokens: list[str] = []
    for part in re.findall(r'[\u4e00-\u9fff]{2,}|[a-z0-9_]+', str(text or '').lower()):
        tokens.append(part)
        if re.search(r'[\u4e00-\u9fff]', part):
            tokens.extend(part[index : index + 1] for index in range(len(part)))
            tokens.extend(part[index : index + 2] for index in range(max(0, len(part) - 1)))
            tokens.extend(part[index : index + 3] for index in range(max(0, len(part) - 2)))
    return [token for token in tokens if token.strip()]


def embed_text(text: str) -> tuple[list[float], float]:
    """生成无外部依赖的确定性回退向量。"""
    vector = [0.0] * VECTOR_DIM
    for token in tokenize(text):
        digest = blake2b(token.encode(), digest_size=4).digest()
        vector[int.from_bytes(digest, 'big') % VECTOR_DIM] += 1.0
    norm = sqrt(sum(value * value for value in vector))
    if norm:
        vector = [round(value / norm, 6) for value in vector]
    return vector, norm


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """计算两个同空间向量的余弦相似度。"""
    if not left or not right:
        return 0.0
    return max(-1.0, min(1.0, sum(a * b for a, b in zip(left, right))))


def lexical_similarity(query: str, text: str) -> float:
    """按中文 n-gram 集合计算可解释的词面相似度。"""
    left = set(tokenize(query))
    right = set(tokenize(text))
    if not left or not right:
        return 0.0
    return round(len(left & right) / len(left | right), 4)
