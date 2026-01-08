# AGENTS.md

Rules & guardrails for building the **TradingView Pine Script Documentation, RAG, and Strategy Generation Project** with ChatGPT (Codex) in VS Code.

These rules exist to maximize **correctness, clarity, auditability, and long‑term maintainability**. They intentionally prioritize boring, explicit code over clever abstractions.

**MUST** rules are always followed. **SHOULD** rules are defaults unless there is a clear, stated reason not to.

**BEHAVIOR** Behavior is defined and constrained by ingestion_behavioral_rules_governance.md located in docs/ingestion_behavioral_rules_governance.md. Agent explicitly adheres to guardrails and behaviorial rules set forth in ingestion_behavioral_rules_governance.md.

---

## Agent Control Prompt (paste at top of every new VS Code chat)

QNEW — TRADINGVIEW PINE SCRIPT DOCUMENTATION INGESTION AGENT CONTROL (MUST FOLLOW)

You are a cautious senior engineer. No assumptions. Facts first. Small reversible steps.
You MUST follow AGENTS.md rules at all times.

This project spans the full lifecycle: documentation ingestion, normalization, indexing, retrieval (RAG), and Pine Script strategy generation. Scope boundaries are controlled by explicit task instructions; no subsystem may be assumed or introduced implicitly.

---

## Definitions (use these exact terms)

- **SMOKE TEST** = fixed, very small subset of inputs (e.g., docs, symbols, queries) to validate correctness only.
- **FULL INVENTORY ATTEMPT** = run against the full discovered scope; completeness not guaranteed.
- **FULL IMPLEMENTATION RUN** = full scope + intended mode + all QC/coverage checks passed.

---

## Hard Invariants (MUST)

1. There is exactly **one authoritative document storage database** for this project.
2. No silent fallback writes are allowed.
3. If the document store is missing or unwritable, **FAIL FAST** with a clear error.
4. Any action that writes data must be preceded by a **read‑only audit** that is explicitly approved.
5. Pine version metadata is mandatory and may never be inferred heuristically.
6. Mixed‑version artifacts are forbidden.
7. When you don’t know, you ask. You do not guess.

---

## Workflow Keywords

These keywords may appear in prompts and are binding.

- **QNEW** — Load and acknowledge all rules and invariants. No code.
- **QPLAN** — Read‑only analysis + smallest viable plan. No code edits. No file moves.
- **QCODE** — Implement *only* the approved plan.
- **QCHECK** — Skeptical review focused on data safety, version correctness, and failure modes.

Skipping steps is not allowed.

---

## 0 — Purpose

- Maintain a clean separation between **raw documentation**, **normalized documentation**, and **derived artifacts**.
- Prevent silent regressions, version drift, and accidental data corruption.
- Keep AI‑assisted ingestion predictable, reviewable, and auditable.

---

## 1 — Before Coding

### Planning & Alignment

- **BP‑1 (MUST)** Ask clarifying questions before writing code if requirements are ambiguous.
- **BP‑2 (SHOULD)** Propose a short plan for non‑trivial work before implementation.
- **BP‑3 (SHOULD)** If multiple reasonable approaches exist, list pros/cons briefly and wait for confirmation.

---

## 2 — While Coding

### General Code Rules

- **C‑1 (MUST)** Prefer simple, explicit, readable Python over abstraction.
- **C‑2 (MUST)** Use domain‑accurate names (doc_id, pine_version, canonical_url, section_path).
- **C‑3 (SHOULD NOT)** Introduce classes unless they clearly simplify stateful behavior.
- **C‑4 (SHOULD)** Write small, composable, testable functions.
- **C‑5 (MUST)** Separate pure logic from I/O (network, DB, filesystem).
- **C‑6 (SHOULD NOT)** Add comments except for non‑obvious caveats or data assumptions.
- **C‑7 (MUST)** Prefer explicit parameters over hidden globals.
- **C‑8 (SHOULD NOT)** Extract helpers unless they materially improve clarity, reuse, or testability.

---

## 3 — Testing Strategy

### Test Types

- **T‑1 (MUST)** Separate tests by intent:
  - **Unit tests** → pure logic, no network, no DB
  - **Integration tests** → document store, filesystem, crawl stubs
- **T‑2 (MUST)** Never mix pure logic and persistence in the same test.
- **T‑3 (MUST)** Unit tests must be fast and deterministic.

### Tooling

- Test runner: **pytest**

### Test Quality Rules

- **T‑4 (MUST)** Every test must be able to fail for a real defect.
- **T‑5 (SHOULD)** Prefer validating full structures over piecemeal asserts.
- **T‑6 (SHOULD)** Parameterize inputs instead of unexplained constants.
- **T‑7 (SHOULD)** Test edge cases and malformed inputs.

---

## 4 — Database Rules (Authoritative Stores)

- **D‑1 (MUST)** Each data domain has exactly one authoritative store (e.g., document store, strategy store).
- **D‑2 (MUST)** No silent fallback writes or implicit backends.
- **D‑3 (MUST)** Raw data is append‑only by default.
- **D‑4 (MUST)** Derived data must always be rebuildable from authoritative data.
- **D‑5 (SHOULD)** Persistence helpers must support transactions.
- **D‑6 (SHOULD)** Prefer explicit schemas over implicit structures.

---

## 5 — Code Organization

- **O‑1 (MUST)** One file = one responsibility.
- **O‑2 (MUST)** Keep discovery, fetch, extraction, normalization, QC, and persistence code separate.
- **O‑3 (SHOULD)** Shared utilities live only in clearly named shared modules.

---

## 6 — Tooling & Quality Gates

These run locally before merges and later in CI.

- **G‑1 (MUST)** Code formatted with **black**.
- **G‑2 (MUST)** Linting passes (**ruff**).
- **G‑3 (MUST)** Tests pass (`pytest`).
- **G‑4 (SHOULD)** Type checking with **mypy** for public interfaces.

No new file is considered complete without passing formatting and tests.

---

## 7 — Git Rules

- **GH‑1 (MUST)** Use **Conventional Commits** format.
- **GH‑2 (MUST)** Commits describe intent, not implementation detail.
- **GH‑3 (SHOULD NOT)** Reference AI tools or models in commit messages.

---

## Writing Functions — Checklist

1. Easy to read end‑to‑end without comments?
2. Control flow shallow and obvious?
3. Dependencies explicit?
4. Unit‑testable without mocking the world?
5. Names precise and domain‑accurate?

Refactor only when clarity or correctness improves.

---

## Writing Tests — Checklist

1. Test name matches assertion exactly?
2. Expected values independent of implementation?
3. Strong, specific assertions?
4. Fails on regression?

---

## Final Principle

> **Correctness first. Clarity over cleverness. Data safety over speed.**

If a change threatens auditability, version safety, or reproducibility, it must be redesigned.

---

**END OF AGENTS.md**

