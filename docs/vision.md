# AHJIN 2.0 — Vision & Core Philosophy

## 1. Mission

AHJIN 2.0 is an Agentic AI Operating Layer (AIOS). It manages intelligence models, execution harnesses, memory systems, and tools in a unified personal AI system.

## 2. What AHJIN Is and Is Not

### AHJIN IS:
- A personal Agentic AI Operating Layer (AIOS-like system).
- A flagship engineering project for modular agent runtime design.
- A platform for advanced agent, memory, context, and multimodal experimentation.
- A research-ready framework built on clean architectural boundaries.

### AHJIN IS NOT:
- A simple Telegram bot or chatbot wrapper.
- A basic RAG application.
- A hardcoded model script or wrapper around a single API.
- A claim of AGI (Artificial General Intelligence).

## 3. Core Philosophy: THE MODEL IS NOT AHJIN

A basic LLM app looks like:
```
USER ──► LLM ──► ANSWER
```

AHJIN looks like an operating layer:
```
USER
  │
INTERFACE ADAPTER
  │
AHJIN CORE
  │
BERU (Cognitive Orchestration)
  │
HARNESS (Runtime Execution) ──► ContextAssembler / ProviderGateway / ToolExecutor
  │
PROVIDERS / MEMORY / TOOLS
  │
OBSERVATION & VERIFICATION
  │
USER
```

## 4. Development Principle: ARCHITECT BROADLY, IMPLEMENT VERTICALLY

- **Architect Broadly:** Define subsystem boundaries, interfaces, and contracts for the entire long-term vision upfront.
- **Implement Vertically:** Build minimal slices end-to-end (e.g., Phase 1 vertical spine) before expanding complexity.
