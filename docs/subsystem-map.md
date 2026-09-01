# AHJIN 2.0 — Subsystem Map

| Subsystem | Primary Responsibility | Status | Owns | Does NOT Own |
|---|---|---|---|---|
| **Interfaces** | Adapter conversion to/from `TaskRequest` | CURRENT (Telegram) / FUTURE (Web, Desktop) | Protocol translation, chat session mapping | Core business logic, routing |
| **AHJIN Core** | Task entry, dispatch, session registry | CURRENT (Minimal) | Session mapping, task dispatch | Cognitive planning, model calls |
| **BERU** | Cognitive orchestration & planning | CURRENT (Trivial 1-step) | Intent, capability requirements, execution plans, replanning | Prompt building, HTTP, retries, memory DB |
| **Harness** | Execution runtime management | CURRENT (Minimal) | Task state, step runner, retries, timeouts, checkpoints | Planning decisions, concrete model formats |
| **ContextAssembler** | Context retrieval & prompt building | CURRENT (Pass-through) | ContextualizedPrompt assembly, token limit fitting | Model selection, provider formatting |
| **Provider Gateway** | Capability matching & provider dispatch | CURRENT (NVIDIA only) | Provider discovery, capability matching | Prompt building, cognitive reasoning |
| **Model Providers** | Provider API translation | CURRENT (NVIDIA) | Provider HTTP calls, API auth, canonical response mapping | Domain logic, task state |
| **Tools Subsystem** | External action execution | ARCHITECTURALLY DEFINED | Tool registry, execution normalization | Permission checking (handled by Security) |
| **Security Layer** | Authorization & permission boundary | ARCHITECTURALLY DEFINED | PermissionGate, secret management, audit logging | Tool execution mechanics |
| **Memory Subsystem** | User history, preferences & context | ARCHITECTURALLY DEFINED | Working memory, episodic memory, user facts | Document RAG, model execution |
| **RAG / Knowledge** | External document & web retrieval | ARCHITECTURALLY DEFINED | Embeddings, vector retrieval, BM25 search, citations | User memory, conversation state |
| **Agents** | Specialized multi-step roles | ARCHITECTURALLY DEFINED | Agent roles/workflows, child task creation | Core runtime harness mechanics |
| **Multimodal** | Non-text input/output processing | ARCHITECTURALLY DEFINED | ContentPart, Attachment abstractions | Model routing logic |
| **Verification Loop**| Result validation & recovery signal | ARCHITECTURALLY DEFINED | Step output validation, criteria checking | Replanning decisions (signals BERU) |
| **Automation** | Scheduled & background execution | DEFERRED | Cron triggers, background task queues | Direct core logic modification |
| **Observability** | Telemetry & structured logging | CURRENT (structlog) | Task correlation IDs, structured log records | Research evaluation metrics |
| **Research / Eval** | Offline benchmarking & experiments | ARCHITECTURALLY DEFINED | Experiment tracking, model evaluation benchmarks | Production execution path |
| **Local Compute** | On-device model execution | DEFERRED | Ollama/llama.cpp provider drivers | Core orchestrator logic |
