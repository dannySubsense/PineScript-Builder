# PineScript RAG – Output & Attribution Policy
## Legal‑Safe Response Patterns for Strategy Builder AI

---

## Purpose
This document defines **how the AI agent is allowed to use Pine Script documentation at response time**.

The goal is to:
- Prevent redistribution of TradingView documentation
- Ensure responses are **original, synthetic, and value‑adding**
- Preserve Pine Script correctness through grounding, not copying
- Provide clear internal rules the agent must always follow

This policy applies to **all AI‑generated responses**, including:
- Natural‑language explanations
- Strategy design discussions
- Pine Script code generation
- Debugging and repair suggestions

---

## Core Principle

> **Pine Script documentation is used for grounding and verification, not reproduction.**

The AI agent may *consult* documentation internally but must never behave as a mirror, proxy, or substitute for TradingView’s official manuals.

---

## Allowed Usage Patterns (SAFE)

### 1. Original Explanation
- The agent explains concepts **in its own words**
- Language must be paraphrased and synthesized
- No direct reuse of official phrasing

Example:
- ✅ “This function closes an open position when a condition is met”
- ❌ Copying the reference description verbatim

---

### 2. Code‑First Value

The primary output value must be:
- Original Pine Script code
- Strategy logic
- Structural patterns

Documentation is a *supporting source*, not the output itself.

---

### 3. Summarization, Not Quotation

When referencing documented behavior:
- Use concise summaries
- Focus on implications, constraints, and usage patterns

Hard rule:
- No long quotes
- No full parameter lists copied verbatim
- No reproduction of tables or reference layouts

---

### 4. Canonical Linking (Attribution Without Reproduction)

When appropriate, the agent may:
- Link users to official TradingView documentation
- Encourage verification in the canonical source

Example phrasing:
> “For full parameter definitions, see the official TradingView Pine Script reference.”

Links are allowed. Copying content is not.

---

### 5. Strategy‑Level Reasoning

Responses should emphasize:
- How components work together
- Why a design choice is appropriate
- Tradeoffs and risks

This moves the output away from documentation replacement and toward **expert reasoning**.

---

## Disallowed Usage Patterns (UNSAFE)

The agent must never:

- Reproduce documentation verbatim or near‑verbatim
- Output full reference sections or tables
- Act as a searchable Pine Script manual
- Claim to be an “authoritative replacement” for TradingView docs
- Provide bulk explanations that mirror doc page structure

If a user explicitly requests documentation text, the agent must **refuse politely and redirect**.

---

## Handling Direct Documentation Requests

If the user asks:
- “Show me the Pine Script docs for X”
- “Paste the reference page for Y”

The agent must:
1. Decline to reproduce documentation
2. Offer a summarized explanation instead
3. Provide a link to the official source

This behavior is mandatory.

---

## Interaction With the RAG Layer

### Retrieval Rules
- Retrieved documents are **internal context only**
- Retrieved text must never be exposed directly

### Generation Rules
- All outputs must be synthesized
- Any factual claim must be traceable to retrieved knowledge or internal patterns

---

## Pine Version Safety

- Responses must target **one Pine version at a time**
- Version must be explicit or clearly implied
- Mixed‑version explanations are disallowed

This prevents silent correctness errors.

---

## Auditability & Enforcement

The system should be able to:
- Log which documents were consulted (internal only)
- Flag responses that exceed length or similarity thresholds
- Enforce paraphrase‑only constraints

These controls protect both legal posture and user trust.

---

## Summary

This policy ensures that:
- The AI provides **original, expert‑level value**
- TradingView documentation is respected as the canonical source
- The strategy builder app operates safely, sustainably, and ethically

**Grounding ≠ Redistribution.**

This document is foundational and should be reviewed before any public release or monetization.

