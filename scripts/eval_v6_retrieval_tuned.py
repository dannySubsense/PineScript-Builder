from __future__ import annotations

import json
import math
import re
from pathlib import Path

from sentence_transformers import SentenceTransformer


INDEX_ID = "v6_20260109T152234Z"
TOP_K = 5

DOC_TYPE_BOOST = 0.05
SYMBOL_TYPE_BOOST = 0.05
SECTION_PATH_BOOST = 0.03


def tokenize(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", text.lower()) if token]


def detect_symbol_type_boost(query: str) -> set[str]:
    q = query.lower()
    targets = set()
    if "kw_" in q or "keyword" in q:
        targets.add("kw")
    if "op_" in q or "operator" in q:
        targets.add("op")
    if "an_" in q or "annotation" in q:
        targets.add("an")
    return targets


def section_path_boost(query_tokens: list[str], section_path: str | None) -> bool:
    if not section_path:
        return False
    path_tokens = set(tokenize(section_path))
    for token in query_tokens:
        if token in path_tokens:
            return True
    return False


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    embeddings_path = (
        root / "artifacts" / "embeddings" / "v6" / INDEX_ID / "embeddings.jsonl"
    )
    queries_path = root / "eval" / "v6" / "offline_queries.jsonl"

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    embeddings = []
    with embeddings_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            embeddings.append(json.loads(line))

    vectors = [rec["embedding"] for rec in embeddings]
    vec_norms = [math.sqrt(sum(v * v for v in vec)) for vec in vectors]

    queries = []
    with queries_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            queries.append(json.loads(line))

    hits = 0
    precision_sum = 0.0

    for q in queries:
        qtext = q["query"]
        qvec = model.encode(qtext, normalize_embeddings=False).tolist()
        qnorm = math.sqrt(sum(v * v for v in qvec)) or 1.0
        qtokens = tokenize(qtext)
        symbol_boost_targets = detect_symbol_type_boost(qtext)

        scores = []
        for idx, rec in enumerate(embeddings):
            if rec["pine_version"] != "v6":
                continue
            dot = sum(a * b for a, b in zip(qvec, vectors[idx]))
            denom = qnorm * (vec_norms[idx] or 1.0)
            sim = dot / denom
            score = sim

            if rec["doc_type"] == q["expected_doc_type"]:
                score += DOC_TYPE_BOOST

            if rec["doc_type"] == "reference" and symbol_boost_targets:
                symbol_type = rec.get("symbol_type")
                if symbol_type in symbol_boost_targets:
                    score += SYMBOL_TYPE_BOOST

            if rec["doc_type"] == "guide":
                if section_path_boost(qtokens, rec.get("section_path")):
                    score += SECTION_PATH_BOOST

            scores.append((score, rec))

        scores.sort(key=lambda item: item[0], reverse=True)
        top = scores[:TOP_K]

        expected_doc_type = q["expected_doc_type"]
        expected_url_contains = q["expected_canonical_url_contains"]

        hit = any(
            rec["doc_type"] == expected_doc_type
            and expected_url_contains in rec["canonical_url"]
            for _, rec in top
        )
        hits += 1 if hit else 0

        doc_type_matches = sum(1 for _, rec in top if rec["doc_type"] == expected_doc_type)
        precision_sum += doc_type_matches / TOP_K

    hit_rate = hits / len(queries) if queries else 0.0
    precision = precision_sum / len(queries) if queries else 0.0

    print(f"top_k_hit_rate={hit_rate:.4f}")
    print(f"doc_type_precision={precision:.4f}")


if __name__ == "__main__":
    main()
