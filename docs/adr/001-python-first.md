# ADR-001: Python-First Architecture

## Status
LOCKED / APPROVED

## Context
AHJIN 2.0 requires an orchestration control plane (handling I/O, messaging, task lifecycle) and an AI/research plane (handling embeddings, model inference, RAG, research experiments). We evaluated whether to build TypeScript-first, Python-first, or a hybrid Node/Python system.

## Decision
Adopt **Python-first** (Python 3.12+, `uv`, Pydantic v2, `asyncio`, FastAPI).

## Alternatives Considered
- **TypeScript-first:** Excellent type system, but isolates the system from the Python-native AI/ML ecosystem.
- **Hybrid (TypeScript Control + Python AI):** High ongoing IPC overhead, duplicated schemas, complex multi-runtime deployment.

## Consequences
- Single runtime environment, zero IPC overhead between control plane and AI modules.
- Enforced strict static type checking via `pyright`.
