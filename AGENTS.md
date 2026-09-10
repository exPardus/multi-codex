# Project conventions

Keep the runtime small: one Bash 3.2-compatible executable, plain files, and no
daemon or package dependencies. The optional Codex hook installer may use Python's
standard library. Keep the public command set to spawn, list, result, stop, steer.

Workers must start fresh, exit when done, and retain their selected model on steer.
They may use native Codex subagents, but neither workers nor their subagents may
launch independent workers. Keep the MCX_WORKER guard in place. Default native
subagents to the worker's selected model and effort; never silently inherit an
expensive coordinator model. Keep existing user configuration intact.

For lifecycle changes, run `bash -n mcx`, `shellcheck mcx` when available, and
`python3 -m unittest discover -s tests -v`. Live Codex tests must use small, bounded
prompts. Do not commit job logs, session IDs, authentication data, or local hooks.
