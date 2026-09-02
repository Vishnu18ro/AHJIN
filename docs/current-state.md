# AHJIN 2.0 — Current Implementation State

## 1. Subsystem State Matrix

| Subsystem | State | Notes |
|---|---|---|
| **Architecture** | LOCKED | Master System Blueprint & V2 Execution Architecture |
| **Documentation** | LOCKED | Updated for V2 Multi-Model Routing & Recovery Milestone |
| **Python Runtime** | OPERATIONAL | Python 3.12+, uv, Pydantic v2, asyncio |
| **Package Structure** | OPERATIONAL | Modular monolith (`src/ahjin`) |
| **Model Intelligence** | OPERATIONAL | ModelCatalog, ModelRouter, ModelHealthTracker |
| **Cognitive Orchestration** | OPERATIONAL | BERU Orchestrator & ExecutionStrategy |
| **Execution Runtime** | OPERATIONAL | HarnessRunner, ContextAssembler, ResponseVerifier |
| **Provider Gateway** | OPERATIONAL | ProviderGateway, NvidiaProvider |
| **Interface Adapter** | OPERATIONAL | TelegramAdapter with runtime observability footer & `/health` / `/models` commands |
| **Validation Suite** | OPERATIONAL | 73 automated tests passing (100%), Pyright clean (0 errors), Ruff clean |

---

## 2. Implemented V2 System Architecture

```text
USER (Telegram Client)
    │
    ▼
TELEGRAM ADAPTER (`src/ahjin/interfaces/telegram/bot.py`)
    │  └── Renders response + Runtime Observability Footer & /health /models commands
    ▼
CORE DISPATCHER (`src/ahjin/core/dispatcher.py`)
    │  └── Lifecycle forwarding & request routing (zero business decisions)
    ▼
BERU ORCHESTRATOR (`src/ahjin/beru/orchestrator.py`)
    │  └── Task understanding ──► Emits ExecutionStrategy & CapabilityRequirements
    ▼
HARNESS RUNNER (`src/ahjin/harness/runner.py`)
    │  ├── ContextAssembler (`src/ahjin/harness/context.py`)
    │  └── Execution Loop (enforces require_verification, recovery_policy, max_recovery_attempts)
    ▼
PROVIDER GATEWAY (`src/ahjin/harness/gateway.py`)
    │  └── Delegates selection to ModelRouter (NO production fallback bypass)
    ▼
MODEL ROUTER (`src/ahjin/models/router.py`)
    │  ├── ModelCatalog (`src/ahjin/models/catalog.py`) [FAST vs HEAVY Tiers, Capabilities, Limits]
    │  └── ModelHealthTracker (`src/ahjin/models/health.py`) [Thread-safe Circuit Breakers & Latency EMA]
    ▼
NVIDIA PROVIDER (`src/ahjin/providers/nvidia.py`)
    │  └── API payload serialization, HTTP client, finish_reason mapping
    ▼
NVIDIA API (`https://integrate.api.nvidia.com/v1`)
    │
    ▼
SELECTED MODEL (`nvidia/nemotron-3.5-lightning-30b-a3b` for FAST; `nvidia/nemotron-3-ultra-550b-a55b` for HEAVY)
    │
    ▼
RESPONSE VERIFIER (`src/ahjin/harness/verifier.py`)
    │  └── Structural verification boundary
    ▼
OBSERVATION & SAME-REQUEST RECOVERY (If invocation fails ──► health degraded ──► model excluded ──► rerouted)
```

---

## 3. Subsystem Responsibility Boundaries

- **Core Dispatcher**: Lifecycle management and request forwarding. Pure entry point; contains zero cognitive or model routing logic.
- **BERU Orchestrator**: Strategic cognitive decision engine. Analyzes task text to produce provider-agnostic `ExecutionStrategy` and `CapabilityRequirements`. Contains **ZERO** model IDs, provider IDs, API endpoints, or hardcoded fallback chains.
- **ModelCatalog**: In-memory registry of static `ModelDescriptor` metadata (`model_id`, `provider_id`, `tier`, `capabilities`, `limits`, `priority`, `quality_score`).
- **ModelRouter**: In-memory, zero-latency model selection engine. Evaluates models through a strict 5-pass pipeline:
  1. *Hard Capability Eligibility Gate* (incapable models can **never** beat capable models)
  2. *Health Availability Filter*
  3. *Hard Latency Constraint Pass* (`max_latency_ms`)
  4. *Tier Preference Match* (`FAST` vs `HEAVY`)
  5. *Ranking Pass* (`quality_score` $\times$ `quality_weight` + `priority` - `latency_penalty` + `endpoint_verified` micro tie-breaker)
- **ModelHealthTracker**: Dynamic operational health tracking. Manages model health states, consecutive failures, circuit breakers, and latency Exponential Moving Average (EMA). Protected by `threading.Lock`.
- **Harness Runner**: Step sequencing, verification, and failure recovery loop. Executes strategy policies (`require_verification`, `recovery_policy`, `max_recovery_attempts`) and builds `RuntimeInfo` for observability.
- **Provider Gateway**: Translates execution strategy requirements into concrete `(Provider, ModelID)` selections via `ModelRouter`. Raises `KeyError` explicitly if a provider is unknown (no silent production bypass).
- **NVIDIA Provider**: External HTTP API integration. Handles OpenAI-compatible chat completions requests, header authorization, JSON parsing, and finish reason mapping (`length` $\to$ `MAX_TOKENS`, `stop` $\to$ `COMPLETE`).
- **Telegram Adapter**: Interface adapter. Translates Telegram updates to canonical `TaskRequest` domain types, handles 4096-character message chunking, appends the compact runtime footer to final chunks, and serves diagnostic commands (`/health`, `/models`).
- **Response Verifier**: Structural output verification boundary. Validates output text non-emptiness before returning to callers.

---

## 4. Dynamic Model Health Architecture

Model operational health is dynamic and observed from real traffic:

```text
HEALTHY
   │  (operational failure recorded)
   ▼
DEGRADED
   │  (consecutive failures >= 3)
   ▼
UNHEALTHY
   │  (cooldown expired: model becomes eligible for probe)
   ▼
RECOVERY PROBE ELIGIBLE
   │  (empirical successful invocation recorded)
   ▼
HEALTHY
```

### Key Health Rules:
1. **Evidence-Based Recovery**: Cooldown expiration alone does **NOT** restore `HEALTHY` status. Health restoration requires an empirical successful invocation (`record_success()`).
2. **Dynamic Operations**: Health state updates automatically on real invocations. A `DEGRADED` model remains eligible for routing; an `UNHEALTHY` model enters circuit breaker cooldown.
3. **Decoupled Architecture**: Static `ModelCatalog` metadata and dynamic `ModelHealthTracker` state remain 100% separate.

---

## 5. Same-Request Failure Recovery

- **Recovery Strategy**: Governed by `ExecutionStrategy.recovery_policy` (`REROUTE` vs `FAIL_FAST`) and `max_recovery_attempts` (default `2`).
- **Bounded Budget**: `max_recovery_attempts = 2` means 1 primary attempt + at most 1 alternate model reroute attempt. This prevents unbounded latency or retry loops ($2 \times 35\text{s} = 70\text{s}$ wall-clock limit).
- **Request Isolation**: `excluded_model_ids` is request-local (`set()`), preventing failure exclusions in Request A from contaminating parallel Request B.
- **Explicit Failure Boundary**: If the recovery budget is exhausted or capabilities are unavailable, HarnessRunner surfaces a clean `INVOCATION_FAILED` error.

---

## 6. Runtime Observability & Commands

### Telegram Runtime Footer Format:
```text
━━━━━━━━━━━━━━━━
⚡ AHJIN Runtime
Model: Nemotron Lightning 30B
Route: FAST
AHJIN: 16ms
Model: 25032ms
Total: 26234ms
Path:  Direct
Health: 🟢 Healthy
━━━━━━━━━━━━━━━━
```
*(If same-request rerouting occurs, `Path: ↪ Rerouted`, `From: <failed model>`, and `Reason: <cause>` are displayed.)*

### Diagnostic Commands (`/health` & `/models`):
Produces a compact live snapshot of current model health states and latency EMAs from `ModelHealthTracker`:
```text
AHJIN Model Health

🟢 Nemotron Lightning 30B [FAST]
   Healthy · EMA 25.0s

🟡 Nemotron Ultra 550B [HEAVY]
   Degraded · 1 failure · no latency data

🟡 DeepSeek V4 Pro [HEAVY]
   Degraded · 1 failure · no latency data

🟢 DeepSeek V4 Flash [HEAVY]
   Healthy · no latency data
```

---

## 7. Real-World Validation History

Verification is categorized strictly by evidence source:

1. **Real Telegram E2E Verification (Live NVIDIA Remote API)**:
   - **Simple Task (`"Hi"`)**: Routed to `FAST` tier (`nvidia/nemotron-3.5-lightning-30b-a3b`). Response delivered successfully in `26.2s` (`16ms` AHJIN internal, `25.0s` API) with `Direct` path and `🟢 Healthy` footer.
   - **Reasoning Task (`"Explain quantum physics..."`)**: Routed to `HEAVY` tier (`nvidia/nemotron-3-ultra-550b-a55b`). Model 1 timed out after 35s; health degraded to `🟡 DEGRADED`. Same-request recovery rerouted to Model 2 (`deepseek-ai/deepseek-v4-pro-0813`), which also timed out after 35s. Bounded recovery budget ($2/2$ attempts) exhausted $\to$ surfaced clean `INVOCATION_FAILED` error.
   - **Live Health Diagnostics**: Sent `/models` command in Telegram chat. Response accurately rendered live operational state (`Nemotron Lightning 🟢 Healthy`, `Nemotron Ultra 🟡 Degraded`, `DeepSeek V4 Pro 🟡 Degraded`).

2. **Automated Integration & Unit Testing**:
   - 73 tests passing (100%), including multi-word vision phrase detection, `require_verification` toggle, `FAIL_FAST` policy, `quality_preference` ranking, `max_latency_ms` filtering, evidence-based health recovery, and concurrent request isolation.

3. **Simulated Reroute Testing**:
   - `test_same_request_rerouting_observability` verified full footer rendering for `↪ Rerouted` paths with explicit error classification (`network error`, `timeout`, `verification failure`).

---

## 8. Validation Status
- **Pytest**: `73 passed in 1.57s`
- **Ruff**: `All checks passed!`
- **Pyright**: `0 errors, 0 warnings, 0 informations`

---

## 9. Current Limitations & Planned Capabilities
- **Streaming Output ("Word-by-Word")**: **NOT YET IMPLEMENTED**. Current V2 returns completed block responses. Progressive streaming is planned as a future capability.
- **Task Requirement Heuristics**: BERU uses deterministic keyword and multi-word phrase matching (`_CODING_KEYWORDS`, `_REASONING_KEYWORDS`, `_VISION_PHRASES`). Richer semantic intent classification without LLM calls is planned for future passes.
