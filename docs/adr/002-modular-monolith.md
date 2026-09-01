# ADR-002: Modular Monolith Strategy

## Status
LOCKED / APPROVED

## Context
We evaluated repository organization: single unstructured package, multi-package monorepo workspace, or microservices day one.

## Decision
Adopt a **Modular Monolith** structure in a single Python package with strict internal boundaries enforced by `import-linter`.

## Alternatives Considered
- **Microservices Day 1:** Excessive operational complexity for a single-developer greenfield project.
- **Unstructured Package:** High risk of circular dependencies and tight coupling.

## Consequences
- High developer velocity and simple single-container deployment.
- Clear module boundaries make future extraction of background workers or GPU inference processes straightforward.
