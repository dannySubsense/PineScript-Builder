# Ingestion Behavioral Rules & Governance
## Pine Script Documentation Pipeline

---

## Purpose
This document defines **behavioral and governance-level rules** that constrain how agents and contributors interact with the Pine Script documentation ingestion pipeline.

It exists to:
- Prevent scope creep
- Prevent silent data corruption
- Preserve version correctness
- Enforce review discipline

---

## Relationship to Other Docs

- This document governs *behavior*
- The PRD/SDD governs *architecture*
- Agent Rules govern *execution mechanics*

Conflicts are resolved in the above order.

---

## Core Behavioral Rules

### Rule 1 — Ask Before Acting
If requirements, schemas, or side effects are unclear:
- The agent must stop
- Ask clarifying questions
- Propose options if relevant

---

### Rule 2 — No Silent Assumptions
The agent must never:
- Invent fields
- Guess API shapes
- Assume defaults

Uncertainty must be explicit.

---

### Rule 3 — Scope Respect
The agent must not:
- Introduce RAG concepts
- Introduce vector DB logic
- Introduce Pine code generation logic

All such work is deferred.

---

### Rule 4 — Change Scope Discipline
Any change must declare:
- What is changing
- What is not allowed to change

Undeclared changes are failures.

---

### Rule 5 — Version Safety

- Pine version is mandatory everywhere
- Mixed-version artifacts are forbidden
- Ambiguity causes hard failure

---

### Rule 6 — Review Before Persistence

- Any write must be preceded by a read-only audit
- QC failures block persistence

---

## Human-in-the-Loop Gates

The following require explicit approval:
- Schema changes
- Ingestion strategy changes
- Version handling changes
- Storage backend changes

---

## Enforcement Philosophy

- Prefer blocking over guessing
- Prefer correctness over speed
- Prefer explicit design over clever shortcuts

---

## Final Statement

> **This pipeline is an infrastructure asset, not an experiment.**

Behavior that jeopardizes auditability or correctness is unacceptable.

---

**END OF DOCUMENT**

