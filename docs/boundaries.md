# AHJIN 2.0 — Architectural Boundaries & Rules

## 1. Non-Negotiable Rules

1. **Interfaces do not know concrete providers.** Interface adapters speak only to `AHJIN Core` using `TaskRequest` and `TaskResult`.
2. **BERU owns cognitive orchestration, NOT execution.** BERU decides *what* needs to be done. It does not execute tools, handle HTTP retries, or build prompts.
3. **BERU does not become a dumping ground.** BERU must not contain prompt formatting, memory DB calls, or provider SDK wrappers.
4. **Harness owns execution runtime, NOT decisions.** The Harness runs plans. If a decision or replan is needed, it signals BERU.
5. **ContextAssembler lives inside Harness.** It receives state from prior steps and builds `ContextualizedPrompt`.
6. **Providers isolate provider specifics.** Raw NVIDIA JSON, HTTP headers, and SDK objects never escape the provider module.
7. **Memory ≠ RAG.** Memory stores user facts and conversation context. RAG retrieves document knowledge. They are distinct subsystems.
8. **Agent ≠ Model.** Agents are structured workflows. Models are intelligence resources used by agents through the Harness.
9. **Tools must pass through PermissionGate.** No tool runs without passing security checks.
10. **Research is an observer.** Research/eval infrastructure reads production logs and contracts; it is never in the critical execution path.

## 2. Dependency Direction Rules

```
Interfaces ──► Core ──► BERU ──► Harness ──► ContextAssembler / ProviderGateway ──► Providers
```

- No reverse dependencies.
- No cross-layer shortcut imports (e.g., Interface direct to Provider).
- Enforced via static `import-linter` rules in CI.
