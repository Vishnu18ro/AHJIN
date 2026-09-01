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
- **Implementation Fix (Non-Architectural):** Resolved a Telegram polling lifecycle issue where `start()` returned prematurely after `start_polling()`. Added an `asyncio.Event()` wait to keep the event loop active during polling.
- **Validation:** Distinguishes automated unit/linter tests, simulated mapper tests, and live real-world end-to-end testing.

### 6. Provider Abstraction & Model Config Isolation
- **Architectural Validation:** Changing model configuration via `NVIDIA_MODEL_ID` in `.env` required zero changes to Core, BERU, Harness, or Telegram adapter code.
- **Runtime Observations:** Recorded empirical provider-side observations (e.g., DeepSeek model timeouts vs `nvidia/nemotron-3.5-lightning-30b-a3b` responsiveness) as temporary operational states rather than permanent architectural decisions.

### 7. V1 Spine Latency Profiling & Empirical Diagnosis
- **Measurement Goal:** Quantify exact latency distribution across all 11 stages of the V1 execution spine for trivial user requests (`"Hi"`, `"Hello"`, `"What is 2+2?"`).
- **Empirical Results:**
  - AHJIN internal latency (Core Dispatcher, BERU Orchestrator, Harness Runner, ContextAssembler, ProviderGateway): **< 1.0 ms** (< 0.01% of total time).
  - External NVIDIA API HTTP network & GPU inference latency: **11.07s – 17.21s** (99.9% – 100% of total user-perceived delay).
- **Diagnosis:** AHJIN internal code overhead is zero-friction. Latency is entirely attributable to non-streamed HTTP completion generation on remote NVIDIA GPU infrastructure.

