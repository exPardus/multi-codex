# Changelog

## Unreleased

- Allow workers to use native Codex subagents while blocking independent worker
  launches. Native subagents default to the worker's model and reasoning effort.
- Install `mcx` and `multicodex` on PATH alongside the Codex startup hook.
- Preserve unrelated commands and hooks, including handlers in a shared group.
- Prefer the short `mcx` command in coordinator startup instructions.
- Add a visual project overview, expanded usage guide, and contribution notes.

## 2026-09-10 · Initial version

- Five commands: `spawn`, `list`, `result`, `stop`, and `steer`.
- Independent background workers with plain local state and no persistent daemon.
- Luna/medium defaults, per-worker model selection, and saved settings on resume.
- Global startup context, worker identity, and guards against recursive spawning.
- Process group cleanup and a fix for completion racing with status inspection.
- Offline lifecycle tests on Linux and macOS, plus live Codex smoke checks.
