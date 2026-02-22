# Coordinator Lessons

### [Coordinator] — 2026-02-23 | Mistake: Skipped Phase 5 (plan review) and implemented code directly instead of dispatching to machine_learning subagent | Rule: Phase 5 is a hard gate — present the plan, ask the confirmation question, and stop. Do not touch any file or invoke any agent until the user explicitly confirms. All production code changes must go through the appropriate subagent via `runSubagent`, never implemented directly by the coordinator.
