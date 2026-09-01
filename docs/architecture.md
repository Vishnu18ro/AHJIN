# AHJIN 2.0 — System Architecture

## 1. Executive Architecture

AHJIN 2.0 separates cognitive decision-making from runtime execution and model providers:

```
┌───────────────────────────────────────────────────────────┐
│                    INTERFACE LAYER                        │
│   Telegram Adapter (v1) │ Web │ Desktop │ Voice (future)  │
└─────────────────────────────┬─────────────────────────────┘
                              │ TaskRequest
┌─────────────────────────────▼─────────────────────────────┐
│                       AHJIN CORE                          │
│     Session Management │ Dispatcher │ Event Routing       │
└─────────────────────────────┬─────────────────────────────┘
                              │ TaskRequest
┌─────────────────────────────▼─────────────────────────────┐
│              BERU (Cognitive Orchestration)               │
│   Intent Extraction │ Planning │ Capability Requirements │
└─────────────────────────────┬─────────────────────────────┘
                              │ ExecutionPlan
┌─────────────────────────────▼─────────────────────────────┐
│                 HARNESS (Execution Runtime)               │
│   Task Lifecycle │ Step Execution │ Retries │ State       │
│                                                           │
│   ┌────────────────────┐   ┌──────────────────────────┐   │
│   │  ContextAssembler  │   │     ProviderGateway      │   │
│   │ (retrieves/builds) │   │ (matches capability)     │   │
│   └─────────┬──────────┘   └────────────┬─────────────┘   │
└─────────────┼───────────────────────────┼─────────────────┘
              │                           │
   ┌──────────▼──────────┐     ┌──────────▼──────────┐
   │ Memory / RAG (fut.) │     │ Model Providers     │
   └─────────────────────┘     │ NVIDIA (v1)         │
                               └─────────────────────┘
```

## 2. Request & Control Flow

1. **Interface Layer:** Normalizes incoming updates to `TaskRequest`.
2. **AHJIN Core:** Registers session and hands `TaskRequest` to BERU.
3. **BERU:** Assesses task complexity, determines capabilities needed, produces `ExecutionPlan`.
4. **Harness:** Takes `ExecutionPlan`, sequences `PlanStep` execution.
5. **ContextAssembler (inside Harness):** Combines history, instructions, and future memory into `ContextualizedPrompt`.
6. **ProviderGateway (inside Harness):** Matches `CapabilityRequirements` to concrete provider (`NvidiaProvider`).
7. **NvidiaProvider:** Translates `ContextualizedPrompt` to NVIDIA API format and invokes model endpoint.
8. **ModelInvocationResponse:** Returned canonically to Harness.
9. **TaskResult:** Harness packages step results into `TaskResult`, returned via Core to Interface.

## 3. Core Architectural Boundaries

- **BERU vs Harness:** BERU decides *what* to do. Harness decides *how* to execute it.
- **ContextAssembler Boundary:** Context assembly happens inside Harness, receiving state from prior steps.
- **Provider Gateway:** Models are behind abstract interfaces (`BaseModelProvider`). Core and BERU never import concrete providers.
