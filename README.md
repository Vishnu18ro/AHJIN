# AHJIN 2.0 — Personal Agentic AI Operating Layer

AHJIN 2.0 is a greenfield personal Agentic AI Operating Layer (AIOS). It orchestrates intelligence, memory, tools, and execution harnesses to create an autonomous personal system.

> **Current Status:** Phase 2 V2 Multi-Model Routing, Execution Strategy & Bounded Recovery Operational & Verified Real-World (Telegram ──► Core ──► BERU ──► ModelRouter ──► Harness ──► ProviderGateway ──► NVIDIA Provider).

---

## 📚 Documentation Map

Follow this reading path to understand AHJIN 2.0:

1. **[Vision Document](docs/vision.md)** — Core philosophy, AIOS concept, long-term goals.
2. **[Current State](docs/current-state.md)** — Operational status, V2 multi-model routing architecture, dynamic health model, real-world validation evidence, and observability footers.
3. **[Architecture](docs/architecture.md)** — Executive system architecture and request flow.
4. **[Subsystem Map](docs/subsystem-map.md)** — Deep dive into all 18+ subsystems.
5. **[Architectural Boundaries](docs/boundaries.md)** — Hard rules, dependency directions, non-negotiables.
6. **[Canonical Contracts](docs/contracts.md)** — Domain contracts and ContextAssembler boundary.
7. **[System Evolution](docs/evolution.md)** — Capability-gated phased progression roadmap.
8. **[Architecture History](docs/architecture-history.md)** — Decisions made, legacy removal, V1/V2 milestone verification logs.
9. **[Architecture Decision Records (ADRs)](docs/adr/)** — Formal records of key technical decisions:
   - [ADR-001: Python-First Architecture](docs/adr/001-python-first.md)
   - [ADR-002: Modular Monolith Strategy](docs/adr/002-modular-monolith.md)
   - [ADR-003: Canonical Domain Contracts](docs/adr/003-canonical-contracts.md)
   - [ADR-004: Master System Blueprint](docs/adr/004-master-system-blueprint.md)

---

## ⚡ Core Philosophy

- **THE MODEL IS NOT AHJIN.** AHJIN is the complete operating layer surrounding model intelligence.
- **ARCHITECT BROADLY. IMPLEMENT VERTICALLY.** Broad architecture defined now; implementation grows incrementally.
- **STRICT BOUNDARIES.** Clean separation between interfaces, cognitive planning (BERU), execution runtime (Harness), model routing (ModelRouter), and providers.
