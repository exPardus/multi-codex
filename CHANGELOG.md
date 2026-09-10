# Changelog

## 0.2.0

- Add `spawn --wait` and `steer --wait` for harness-managed background commands.
  Each waiter follows one run, returns its exit status, and cancels only that run.
- Add `never`, `auto`, and `unrestricted` worker approval modes, with global/local
  config and `MCX_APPROVAL` overrides. Steering preserves the saved mode.

## 0.1.0

- Package native Codex and Claude Code plugins with one shared mcx skill and hook.
- Add `install.py` targets for either app, both apps, or PATH commands only.
- Migrate the legacy global hook after successful plugin installation.
- Keep startup context brief and load detailed guidance through the skill on demand.
- Request concise worker results with verification evidence and blockers.

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
