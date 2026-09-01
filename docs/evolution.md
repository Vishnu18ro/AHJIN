# AHJIN 2.0 — System Evolution Roadmap

Capability-gated progression roadmap:

```
Phase 1: Vertical Spine (Telegram ──► Core ──► BERU ──► Harness ──► NVIDIA)  [STATUS: OPERATIONAL & VERIFIED]
   │
Phase 2: Model Abstraction + Capability-Aware Selection + Multi-Model Routing  [STATUS: NEXT PHASE]
   │
Phase 3: Tools & Security (ToolRegistry, PermissionGate, retries)
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
- **Operational Model:** `meta/llama-3.2-11b-vision-instruct` (Temporary operational V1 model).
- **Verification:** Unit tests, static typing (Pyright), linting (Ruff), import boundaries (Import-Linter), and real Telegram message verification.

### Phase 2: Next Direction (Planned)
- **Focus:** Model Abstraction + Capability-Aware Selection + Multi-Model Routing.
