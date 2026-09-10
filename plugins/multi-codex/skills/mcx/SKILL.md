---
name: mcx
description: Use mcx (multi-codex) to launch, collect, steer, or stop independent Codex workers, including delegation from Claude Code. Use when the user requests mcx or background Codex workers.
---

# mcx

Use the shell to run `mcx`. The coordinator can be Codex or Claude Code; workers
always run the authenticated local Codex CLI. No parent transcript is inherited.
Normal Codex configuration and project instructions still load.

If `MCX_WORKER=1`, you are already a worker: finish your assigned task. You may
use native Codex subagents with your selected model and effort, but you and those
subagents must not launch independent workers, steer workers, or unset the
marker. Collect and close native subagents before returning your final answer.

## Delegate a task

Run from the intended project directory. Supply the objective, relevant context,
permitted files, constraints, and how to verify success. Request a concise outcome,
file locations, checks/results, and unresolved blockers; keep full logs in files.
Pass relevant excerpts or file paths rather than copying a conversation history.
Prefer a quoted heredoc for
long instructions so the shell does not expand task text:

```sh
mcx spawn --wait - <<'TASK'
Review src/auth for bugs. Read related tests. Do not edit files.
Return concrete findings with file locations and any test gaps.
TASK
```

Run this through the harness's background shell facility. Do not add shell `&`,
use `nohup`, or capture a waiting launch with `id=$(...)`: the harness must track
the command until it exits. The first stdout line is the worker ID. `--wait`
keeps that command alive until this run finishes and returns the worker's exit
code (0 on success, nonzero on failure or interruption). Cancellation via
TERM/INT/HUP stops this run and its children. SIGKILL cannot run cleanup; use
`mcx stop ID` if the harness forcibly killed the launcher.

Save the printed worker ID and keep doing independent work. Assign disjoint files
when workers edit a shared directory; mcx does not create worktrees or merge work.
Keep using that directory, or set an absolute `MCX_DIR`, to find the same jobs.

```sh
mcx list
mcx result ID
mcx steer --wait ID "Check whether token expiry changes your findings."
mcx stop ID
```

`result` exits 2 while running, 0 with an answer, and 1 for failure or an invalid
job. Use the harness's completion notification when available; otherwise collect
the background command through its process/session handle. Background execution
alone does not guarantee the harness will wake an idle coordinator. Read final
answers through `result`; load raw event logs only to investigate a failure. If a job
fails, inspect its `.mcx/ID/log` and `events.jsonl`. Workers exit when done; results
stay on disk. Read and assess the result before treating the delegated task as
complete. Stop workers whose work is no longer needed.

`steer` stops the old process group and resumes the saved conversation in a new
process with the same model, effort, and approval mode, including after completion.
To track the new run, background `steer --wait`; the old waiting command exits
with an interruption status, which is expected. Each waiter tracks one run only.
It replaces local logs and the prior answer; save those first if needed. If no
session ID exists yet, wait briefly and retry.

Without `--wait`, `spawn` and `steer` return the ID immediately and detach. Use
that mode when work should survive the launching shell closing, and check
`list`/`result` periodically while doing useful work. Avoid tight polling.

## Models and availability

Default: `gpt-5.6-luna` / `medium`. Use Luna for small bounded tasks. Select Terra
for harder coding or Sol for complex tasks. Use `gpt-6-astra` only when the user
specifically requests it. Native subagent defaults match their worker.

```sh
mcx spawn -m gpt-5.6-terra -r high "Fix the parser and run its tests."
```

`MCX_MODEL` and `MCX_EFFORT` set shell defaults. Do not copy an expensive
coordinator model automatically. Spawn only the workers the task needs.

If `mcx` is absent from PATH, use the absolute launcher path supplied by the
startup hook, or the bundled `../../mcx` relative to this skill directory.
`python3 install.py cli` from the repository installs PATH commands.
The launching shell must permit background execution and process inspection;
use the host's normal permission flow if required.

## Worker approval mode

The built-in mode is `never`: `workspace-write`, with no approval requests.
`auto` keeps `workspace-write` and routes eligible requests through Codex's
automatic reviewer. `unrestricted` disables both sandboxing and approval prompts.
Use the user's selected mode; do not switch modes to work around a denial.

One optional setting, `approval=never`, `approval=auto`, or
`approval=unrestricted`, can be stored in `${XDG_CONFIG_HOME:-$HOME/.config}/mcx/config`
and the local job directory's `config` (normally `.mcx/config`, keep it untracked).
Precedence: `MCX_APPROVAL` environment variable, then local config, then global
config, then `never`. Config files contain plain key/value data and comments,
not shell commands. For an explicitly requested per-launch override:

```sh
MCX_APPROVAL=auto mcx spawn --wait "Run the tests and report the results."
```

The mode is saved in `.mcx/ID/approval`. Steering preserves it even if config or
environment changes. Older jobs without this file retain `never`. If automatic
review denies a required action, report the blocker in the result.
