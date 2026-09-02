# AHJIN 2.0 — System Evolution Roadmap

Capability-gated progression roadmap:

```text
Phase 1: Vertical Spine (Telegram ──► Core ──► BERU ──► Harness ──► NVIDIA)  [STATUS: OPERATIONAL & VERIFIED]
   │
Phase 2: Model Abstraction + Capability-Aware Selection + Multi-Model Routing  [STATUS: OPERATIONAL & VERIFIED]
   │
Phase 3: Tools & Security (ToolRegistry, PermissionGate, retries)  [STATUS: NEXT PHASE]
   │
Phase 4: Memory & Context (Conversation history, episodic memory, ContextAssembler expansion)
   │
Phase 5: Knowledge / RAG (Document ingestion, vector retrieval, BM25)
   │
Phase 6: Agents & Workflows (AgentRegistry, ResearchAgent, child tasks)
   │
Phase 7: Closed Loop & Verification (Verifier, replanning signal)
   │
Phase 8: Multimodal & Local Compute (Vision inputs, Ollama/llama.cpp providers)
   │
Phase 9: Research & Evaluation (Benchmark suite, experiment tracking)
```

## Milestone Log

### Phase 1: Vertical Spine Operational (Completed)
- **Status:** VERIFIED REAL-WORLD END-TO-END.
- **Scope Achieved:** Real Telegram message ──► `TelegramAdapter` ──► `TaskDispatcher` ──► `BeruOrchestrator` ──► `HarnessRunner` (`ContextAssembler`) ──► `ProviderGateway` ──► `NvidiaProvider` ──► NVIDIA API ──► Telegram Response.
- **Verification:** Unit tests, static typing (Pyright), linting (Ruff), and real Telegram message verification.

### Phase 2: Multi-Model Routing & Bounded Recovery (Completed)
- **Status:** VERIFIED REAL-WORLD & AUTOMATED SUITE (73 tests passed, Pyright clean, Ruff clean).
- **Scope Achieved**:
  - `ModelCatalog` metadata registry (`FAST` vs `HEAVY` tiers, capabilities, limits, quality ratings).
  - In-memory `ModelRouter` (5-pass: Capability Gate ──► Health Filter ──► Max Latency Constraint ──► Tier Match ──► Quality Preference Ranking). Zero LLM calls, zero network I/O during selection.
  - Provider-neutral BERU `ExecutionStrategy` (contains zero model IDs, provider names, or API endpoints).
  - Dynamic `ModelHealthTracker` with evidence-based recovery (cooldown enables probe eligibility; status restored ONLY on successful invocation).
  - Same-request rerouting bounded by `max_recovery_attempts = 2` with request-local `excluded_models`.
  - Telegram runtime observability footer and live `/health` / `/models` diagnostic commands.
  - Progressive streaming output ("word-by-word") is **NOT YET IMPLEMENTED** (planned for future phase).
