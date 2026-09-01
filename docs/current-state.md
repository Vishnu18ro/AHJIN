# AHJIN 2.0 — Current Implementation State

## 1. State Matrix

| Subsystem | State | Notes |
|---|---|---|
| **Architecture** | LOCKED | Full Master System Blueprint approved |
| **Documentation** | LOCKED | Complete docs set written & updated for V1 Milestone |
| **Python Runtime** | OPERATIONAL | Python 3.12+, uv, Pydantic v2, asyncio |
| **Package Structure** | OPERATIONAL | Modular monolith (`src/ahjin`) |
| **Canonical Contracts** | OPERATIONAL | Canonical domain types & ContextAssembler boundary |
| **Application Code** | OPERATIONAL (V1 SPINE) | Full real-world vertical spine verified |
| **Dependencies** | INSTALLED | Managed via `pyproject.toml` and `uv` |

---

## 2. Operational V1 Spine Architecture

The real-world V1 vertical execution spine is fully operational end-to-end:

```
Telegram Client
   │
   ▼
Telegram Adapter (`src/ahjin/interfaces/telegram/bot.py`)
   │
   ▼
Core Dispatcher (`src/ahjin/core/dispatcher.py`)
   │
   ▼
BERU Orchestrator (`src/ahjin/beru/orchestrator.py`)
   │
   ▼
Harness Runner (`src/ahjin/harness/runner.py`)
   │  └── ContextAssembler (`src/ahjin/harness/context.py`)
   ▼
ProviderGateway (`src/ahjin/harness/gateway.py`)
   │
   ▼
NVIDIA Provider (`src/ahjin/providers/nvidia.py`)
   │
   ▼
NVIDIA API Endpoint (`https://integrate.api.nvidia.com/v1`)
   │
   ▼
Active Model (`meta/llama-3.2-11b-vision-instruct`)
   │
   ▼
Model Response ──► Harness ──► BERU ──► Core ──► Telegram Adapter ──► Telegram Client
```

---

## 3. Verification & Operational Status

### Real-World Verification Milestone
Verification of AHJIN 2.0 progressed through distinct tiers:
1. **Automated Unit & Integration Tests**: Pytest, Pyright, Ruff, and Import-Linter validation suites passing 100%.
2. **Simulated Interface Testing**: Programmatic verification via `TelegramMapper` verifying structural request/result mapping.
3. **REAL Telegram End-to-End Testing**: Verified with an actual message sent from a live Telegram client, routed through the full AHJIN spine, executed against the NVIDIA API, and delivered back as a real reply to the Telegram chat.

### Telegram Runtime Fix
During live testing, a concrete implementation defect was identified and resolved:
- **Defect**: `TelegramAdapter.start()` executed `start_polling()` and immediately returned, causing `asyncio.run(main())` to terminate the event loop before updates could be received.
- **Fix**: Implemented a lifecycle event wait (`await self._stop_event.wait()`) keeping the application and event loop alive during polling, with clean shutdown on `KeyboardInterrupt`.
- **Classification**: Historical implementation/lifecycle fix (architecture remains unchanged).

### Temporary Operational Model Configuration
- **Active Model**: `meta/llama-3.2-11b-vision-instruct`
- **Classification**: TEMPORARY CURRENT V1 OPERATIONAL MODEL. This is an operational configuration value set via `.env`, NOT a permanent architectural decision for AHJIN's default intelligence.
- **Observed Runtime Behavior**:
  - `deepseek-ai/deepseek-v4-flash-0731` experienced repeated provider-side timeouts during the live testing window.
  - Other probed models showed varying provider-side availability and response behaviors.
  - These are empirical runtime/provider observations, not permanent architectural decisions or permanent model deprecations.

---

## 4. Architectural Validation & Current Limitations

### Architectural Validation
Changing model selection from `.env` without modifying Core, BERU, Harness, or Telegram code verified the Provider abstraction (`BaseModelProvider` & `ProviderGateway`), confirming the modular monolith's strict separation of concerns.

### Current V1 Limitations
AHJIN V1 is intentionally a working vertical spine, not the completed system:
- Single configured operational model at a time (operator-set via config).
- No intelligent multi-model routing yet.
- No capability-based dynamic model selection yet.
- Memory, RAG, Tool registries, and Agent workflows remain unexpanded for future phases.

---

## 5. Next Major Phase

**Phase 2 / Model Expansion**:
- Model Abstraction + Capability-Aware Model Selection + Multi-Model Routing.
