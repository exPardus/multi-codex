# multi-codex

One Bash script. Five commands. Independent background Codex CLI workers; no
daemon, packages, registry service, or worker limit.

Requires Bash 3.2+ and an installed, authenticated `codex` with `exec --json` and
`exec resume` support. Uses standard Unix utilities; intended for Linux and macOS.

```sh
id=$(./mcx spawn "Inspect src/auth and report bugs. Do not edit files.")
./mcx list
./mcx result "$id"
./mcx steer "$id" "Focus on refresh token expiry."
./mcx stop "$id"

# Longer instructions, including all context the worker needs:
./mcx spawn - < task.txt

# Override the inexpensive default for a harder task:
./mcx spawn -m gpt-5.6-terra -r high "Fix the parser and run its tests."
```

- `spawn` immediately prints an ID. Each worker starts a fresh conversation in
  your current directory. No parent transcript is copied. Codex still loads its
  normal configuration and project instructions such as `AGENTS.md`.
- `list` shows IDs, states, models, reasoning effort, and the first line of each task.
- `result` prints the final answer. Exit codes: **0** finished, **2** still running,
  **1** failed/stopped/lost or invalid input. Errors point to the logs.
- `stop` sends TERM to the worker's process group, then KILL after at most three
  seconds if needed. Completed jobs are left alone.
- `steer` **interrupts and resumes** the worker's own saved conversation with your
  new instruction. It also works after completion. It is not live message
  injection: the current run exits and a new process resumes the same session.
  If Codex has not emitted a session ID yet, retry shortly. Each steer replaces
  the previous run's local logs and answer; Codex keeps the conversation history.

Workers survive the launching shell closing and exit when their task finishes.
There are no idle workers, automatic retries, worktrees, or file merge handling.
Workers in the same directory share files; assign separate files when needed.

Jobs live in `./.mcx/`, with plain prompt, PID, state, log, JSONL events, and result
files. Run commands from the same directory, or set `MCX_DIR` to an absolute path
to use one job folder across projects. Delete finished job folders to clean up.
`CODEX_BIN` can point to another Codex executable or wrapper.

Workers use your existing Codex login, with `workspace-write` and approvals set to
`never` so they can edit the workspace without waiting for input.
The launching environment must permit running Codex. No app configuration is
changed by the launcher. Account usage/rate limits still apply.

## Model choice

Workers explicitly default to **gpt-5.6-luna / medium**, even if the coordinator
uses Astra or extra-high reasoning. `-m MODEL` and `-r EFFORT` override this for a
spawn; `MCX_MODEL` and `MCX_EFFORT` set your preferred defaults. Steering keeps the
worker's saved model and effort. There is no automatic fallback to a larger model.

| Model | Suggested use |
| --- | --- |
| `gpt-5.6-luna` | Small, clearly defined tasks; default |
| `gpt-5.6-terra` | Everyday coding that needs more reasoning |
| `gpt-5.6-sol` | Complex, open-ended work |
| `gpt-6-astra` | Only when deliberately requested |

These choices follow the [Codex model guide](https://learn.chatgpt.com/docs/models?surface=cli).

## Codex startup context

```sh
python3 install-codex.py
```

The optional installer registers `mcx _context` as a global `SessionStart` hook in
`$CODEX_HOME/hooks.json` (normally `~/.codex/hooks.json`), preserving other hooks.
Python 3 is needed only for installation and tests, not for the launcher.
Open `/hooks` in Codex once and trust the **Loading multi-codex context** hook.
Codex requires review of the specific hook definition; this tool does not bypass
hook trust. See the [Codex hooks guide](https://learn.chatgpt.com/docs/hooks).

New local sessions receive the command path and a short usage/model guide.
Workers instead receive explicit worker instructions, including no delegation.
The hook runs at startup, resume, clear, and compaction. Restart existing clients
if needed. Other machines or a different `CODEX_HOME` need their own installation.
If you move this repository, rerun the installer and trust the updated hook.
Remove its entry from `hooks.json` to uninstall; an existing hooks file is backed
up as `hooks.json.mcx-backup` when the installer changes it.

Recursion prevention also works without the global hook: every worker input
contains the worker rules, native Codex subagents are disabled, and `MCX_WORKER=1`
is exported and set explicitly in Codex's shell environment. `mcx spawn` and
`mcx steer` reject calls from workers. This prevents accidental delegation loops;
it is not an isolation boundary against deliberately changing the environment.

To use it from anywhere, put this directory on `PATH` or copy `mcx` into an existing
writable directory on your `PATH`.

Built around Codex's [non-interactive CLI](https://learn.chatgpt.com/docs/non-interactive-mode).

## Tests

```sh
bash -n mcx
shellcheck mcx  # optional development tool
python3 -m unittest discover -s tests -v
```

The offline tests use a fake Codex and exercise real process lifecycles. CI runs
them on Linux and macOS; no credentials or model calls are needed.
