# ADR-004: Master System Blueprint — Architect Broadly, Implement Vertically

## Status
LOCKED / APPROVED

## Context
AHJIN 2.0 is a long-term personal AIOS project. We needed an architectural strategy that preserves the full 18+ subsystem vision without creating premature microservice overhead or empty placeholder code.

## Decision
Adopt **ARCHITECT BROADLY. IMPLEMENT VERTICALLY.**
- Complete subsystem map and boundaries defined and documented upfront.
- Phase 1 vertical spine built first (Telegram ──► Core ──► BERU ──► Harness ──► NVIDIA).
- Subsystems expanded capability-by-capability in subsequent phases.

## Consequences
- Full architecture is explicit in documentation and interface stubs from Day 1.
- No wasted effort on premature complex subsystems (RAG, full memory, local compute) before the core runtime spine is operational.
