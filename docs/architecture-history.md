# AHJIN 2.0 — Architectural History

## Historical Evolution

### 1. Legacy Assumptions Removal
- **Old:** Legacy codebase assumptions, external agent framework assumptions (Hermes), Gemini foundation.
- **Why Changed:** AHJIN 2.0 is designed from first principles.
- **New:** Greenfield reset. Custom harness. Gemini removed. Model-agnostic architecture.

### 2. Runtime Decision: Python-First vs TypeScript
- **Considered:** TypeScript-first, Python-first, Hybrid Node/Python.
- **Decision:** Python-first (Python 3.12+, asyncio, Pydantic v2, uv).
- **Rationale:** AI/ML ecosystem is Python-native. Avoids permanent cross-language IPC overhead.

### 3. Repository Structure: Modular Monolith
- **Considered:** Single package, Monorepo workspace, Microservices Day 1.
- **Decision:** Modular Monolith.
- **Rationale:** Low single-developer overhead, strong internal interfaces via `import-linter`, easy process extraction later.

### 4. Canonical Contracts & Context Boundary
- **Old Proposal:** `PromptSpec` inside BERU's `ExecutionPlan`.
- **Problem:** Forced BERU to become a prompt builder and touch memory/RAG/context limits.
- **Decision:** BERU outputs high-level `ModelStepIntent` and `CapabilityRequirements`. Context assembly moves inside Harness (`ContextAssembler`).

### 5. V1 Real-World Vertical Spine Verification
- **Milestone:** Verification of complete end-to-end runtime loop using real Telegram network messages.
- **Execution Path:** Telegram Client ──► `TelegramAdapter` ──► `TaskDispatcher` ──► `BeruOrchestrator` ──► `HarnessRunner` (`ContextAssembler`) ──► `ProviderGateway` ──► `NvidiaProvider` ──► NVIDIA API ──► Response ──► Telegram Client.

### 6. V2 Multi-Model Routing & Bounded Recovery Milestone
- **Milestone:** Complete implementation and verification of V2 Model Intelligence, ExecutionStrategy, and dynamic circuit breakers.
- **Key Decisions & Verification**:
  - **BERU Neutrality**: BERU outputs `ExecutionStrategy` containing zero model IDs, provider names, or API endpoints.
  - **5-Pass In-Memory Router**: Pure in-memory selection (Capability Gate ──► Health Filter ──► Max Latency Constraint ──► Tier Match ──► Quality Preference Ranking).
  - **Evidence-Based Health Recovery**: Cooldown expiration enables a probe attempt, but status is restored to `HEALTHY` ONLY upon empirical proof of a successful invocation.
  - **Bounded Recovery**: Same-request rerouting is bounded by `max_recovery_attempts = 2` to prevent infinite retry latency loops.
  - **Runtime Observability**: Added Telegram footer and `/health` / `/models` HTML snapshot commands.
  - **Verification**: Verified real Telegram requests ("Hi" fast path, reasoning request timeout recovery, `/models` readout) and 73 automated tests.
