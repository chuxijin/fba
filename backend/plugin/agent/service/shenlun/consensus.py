from __future__ import annotations

import math
import operator
import re

from hashlib import sha256
from typing import Any

FEATURE_HASH_DIMENSIONS = 256


def compact_reference_consensus(  # noqa: C901
    references: list[dict[str, Any]],
    materials: list[dict[str, Any]],
    similarity_threshold: float = 0.62,
) -> dict[str, Any]:
    """对多份参考答案分句聚类，生成 Rubric 构建提示而非直接评分证据。"""
    clauses: list[dict[str, Any]] = []
    for reference in references:
        reference_text = '；'.join(str(reference.get(key) or '') for key in ('answer_text', 'scoring_points', 'notes'))
        clauses.extend(
            {
                'text': clause,
                'reference_id': int(reference['id']),
                'organization': str(reference.get('organization') or f'参考答案{reference["id"]}'),
            }
            for clause in split_semantic_clauses(reference_text)[:24]
        )
    if not clauses:
        return {
            'embedding_model': 'deterministic-feature-hash-v1',
            'organization_count': len(references),
            'clusters': [],
        }

    clusters: list[dict[str, Any]] = []
    for clause in clauses:
        vector = _feature_hash(clause['text'])
        best_cluster: dict[str, Any] | None = None
        best_score = -1.0
        for cluster in clusters:
            score = _cosine(vector, cluster['vector'])
            if score > best_score:
                best_cluster, best_score = cluster, score
        if best_cluster is not None and best_score >= similarity_threshold:
            best_cluster['items'].append(clause)
            if len(clause['text']) < len(best_cluster['representative']):
                best_cluster['representative'] = clause['text']
                best_cluster['vector'] = vector
        else:
            clusters.append({'representative': clause['text'], 'vector': vector, 'items': [clause]})

    material_clauses = [
        {'material_number': material.get('material_number'), 'quote': clause, 'vector': _feature_hash(clause)}
        for material in materials
        for clause in split_semantic_clauses(str(material.get('content') or ''), minimum=8, maximum=120)[:24]
    ][:240]
    organization_count = len(references)
    core_threshold = max(2, (organization_count + 1) // 2)
    output: list[dict[str, Any]] = []
    for index, cluster in enumerate(clusters, start=1):
        organizations = sorted({item['organization'] for item in cluster['items']})
        reference_ids = sorted({item['reference_id'] for item in cluster['items']})
        best_material: dict[str, Any] | None = None
        best_material_score = 0.0
        for material in material_clauses:
            score = _cosine(cluster['vector'], material['vector'])
            if score > best_material_score:
                best_material, best_material_score = material, score
        output.append({
            'cluster_id': f'cluster-{index}',
            'representative': cluster['representative'],
            'reference_ids': reference_ids,
            'organizations': organizations,
            'support_org_count': len(organizations),
            'consensus_candidate': len(organizations) >= core_threshold,
            'material_candidate': {
                'material_number': best_material['material_number'],
                'quote': best_material['quote'],
            }
            if best_material
            else None,
            'material_similarity': round(best_material_score, 4),
        })
    output.sort(key=operator.itemgetter('support_org_count', 'material_similarity'), reverse=True)
    common = [item for item in output if item['support_org_count'] >= 2]
    rare = [item for item in output if item['support_org_count'] == 1][:12]
    return {
        'embedding_model': 'deterministic-feature-hash-v1',
        'preprocessing_mode': 'lightweight',
        'degraded': False,
        'organization_count': organization_count,
        'core_threshold': core_threshold,
        'source_clause_count': len(clauses),
        'material_clause_count': len(material_clauses),
        'clusters': (common + rare)[:36],
    }


def split_semantic_clauses(text: str, minimum: int = 6, maximum: int = 180) -> list[str]:
    clauses: list[str] = []
    for value in re.split(r'[。！？!?；;\n]+', str(text or '')):
        clause = re.sub(r'\s+', ' ', value).strip(' ，、:：')
        semantic_length = len(re.sub(r'[^\w\u4e00-\u9fff]', '', clause))
        if minimum <= semantic_length <= maximum and clause not in clauses:
            clauses.append(clause)
    return clauses


def _feature_hash(text: str) -> dict[int, float]:
    compact = re.sub(r'[^\w\u4e00-\u9fff]', '', str(text or '').lower())
    features = [compact[index : index + 3] for index in range(max(1, len(compact) - 2))]
    if len(compact) < 3:
        features = [compact]
    vector: dict[int, float] = {}
    for feature in features:
        if not feature:
            continue
        digest = sha256(feature.encode()).digest()
        bucket = int.from_bytes(digest[:2], 'big') % FEATURE_HASH_DIMENSIONS
        vector[bucket] = vector.get(bucket, 0.0) + 1.0
    return vector


def _cosine(left: dict[int, float], right: dict[int, float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(index, 0.0) for index, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0
