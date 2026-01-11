# Pine Script Ingestion + Retrieval Playbook (V5/V6)

Purpose: describe the finalized ingestion and retrieval pipeline for Pine Script
documentation with strict version isolation, auditability, and deterministic
artifacts. This is an internal runbook, not a tutorial.

Scope:
- v5 and v6 pipelines (reference and guides where applicable)
- CI-rendered acquisition + agent-driven ingestion
- QC and audit gates
- artifact lifecycle and commit boundaries


## Pipeline Overview (Diagram)

  CI Render (per version)            Agent Ingestion (per version)
  ----------------------             ------------------------------
  Rendered HTML                      Manifest -> Segments -> Normalize
  (reference/guides)      --->       -> RAG index -> Embeddings -> Eval
  commit boundary                      commit boundary at each stage


## Stage Boundaries and Commit Points

1) Rendered acquisition (CI)
   - Output: canonical rendered HTML only
   - Commit: rendered HTML snapshot per run_id

2) Manifest + segmentation (Agent)
   - Output: manifest.json + segments JSONL
   - Commit: manifest + segments together

3) Normalization (Agent)
   - Output: normalized JSONL entities
   - Commit: normalized artifacts only

4) RAG index artifact (Agent)
   - Output: chunks.jsonl + index_meta.json
   - Commit: index artifacts only

5) Local-first embeddings + evaluation (Agent)
   - Output: embeddings.jsonl + embeddings_meta.json
   - Commit: embeddings artifacts only


## CI vs Agent Responsibilities

CI (GitHub Actions)
- Rendered HTML acquisition only.
- No parsing, segmentation, or normalization.
- Deterministic settings (viewport/locale/timezone).

Agent (VS Code)
- Create manifests, segmentation, normalization, RAG artifacts, embeddings.
- Enforce audit gates before any write.
- Enforce v5/v6 isolation and version metadata correctness.


## Version Isolation Rules

- v5 and v6 artifacts are strictly separated by path.
- No cross-version reads or writes in a single run.
- All records require pine_version; no heuristic inference.


## Artifact Layout (Canonical Paths)

Raw rendered (CI)
- raw/rendered/v5/reference/<run_id>/reference.html
- raw/rendered/v6/reference/<run_id>/reference.html
- raw/rendered/v6/guides/<run_id>/<slug>.html

Manifests (Agent)
- raw/rendered/v5/reference/<run_id>/manifest.json
- raw/rendered/v6/reference/<run_id>/manifest.json
- raw/rendered/v6/guides/<run_id>/<slug>.manifest.json

Segments (Agent)
- artifacts/segments/v5/<run_id>.jsonl
- artifacts/segments/v6/<run_id>.jsonl
- artifacts/segments/v6/guides/<run_id>.jsonl

Normalized (Agent)
- normalized/v5/reference_symbols.jsonl
- normalized/v6/reference_symbols.jsonl
- normalized/v6/guide_sections.jsonl

RAG index artifacts (Agent)
- artifacts/rag_indexes/v5/<index_id>/chunks.jsonl
- artifacts/rag_indexes/v5/<index_id>/index_meta.json
- artifacts/rag_indexes/v6/<index_id>/chunks.jsonl
- artifacts/rag_indexes/v6/<index_id>/index_meta.json

Embeddings (Agent, local-first)
- artifacts/embeddings/v5/<index_id>/embeddings.jsonl
- artifacts/embeddings/v5/<index_id>/embeddings_meta.json
- artifacts/embeddings/v6/<index_id>/embeddings.jsonl
- artifacts/embeddings/v6/<index_id>/embeddings_meta.json


## QC and Audit Gates

Audit gate (MUST)
- Read-only audit before any write.
- Confirm version isolation and expected inputs.

Rendered QC
- HTML exists, checksum recorded, anchor counts computed.
- status=complete required for segmentation.

Segmentation QC
- segment_count == anchor_count_total.
- unique anchor_id and segment_id.
- raw_html non-empty.

Normalization QC
- required fields present and non-null.
- pine_version enforced.
- IDs unique.

RAG artifact QC
- chunk_count matches normalized rows.
- doc_type and pine_version enforced.
- body non-empty.

Embeddings QC
- embeddings_written == chunk_count.
- model loads offline.
- evaluation gates met.


## Drift Handling

Reference drift (same version only)
- Compare manifests: anchor_count_delta, prefix deltas, environment deltas.
- Severity: none | low | medium | high.
- Recommended action: ignore | manual_review | resegment | block_pipeline.


## Retrieval and Evaluation (Local-First)

- Embeddings stored as file-based artifacts in-repo.
- Retrieval uses cosine similarity + metadata boosts.
- Offline evaluation set defines acceptance gates per version.


## DO NOT

- Do not mix v5 and v6 artifacts in any run.
- Do not infer pine_version from content.
- Do not write derived artifacts without a read-only audit.
- Do not modify rendered HTML snapshots.
- Do not commit non-canonical artifacts.
- Do not use external vector databases or managed services.

