# AHJIN Research & Evaluation Infrastructure

This package contains offline benchmark suites, prompt evaluation pipelines, and model routing experiments.

## Hard Rules

1. **Read-Only Observer:** Research scripts consume production logs and canonical domain contracts. They never write to production systems.
2. **Forbidden Imports:** Production modules (`core`, `beru`, `harness`, `providers`, `interfaces`) MUST NOT import `ahjin.research`. Enforced via static `import-linter` rules in CI.
