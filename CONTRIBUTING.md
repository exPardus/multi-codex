# Contributing

multi-codex is deliberately small: one Bash executable, five commands, and plain
files. Changes should make that workflow more dependable or easier to use.

## Development

```sh
git clone https://github.com/exPardus/multi-codex.git
cd multi-codex
bash -n mcx
shellcheck mcx
python3 -m unittest discover -s tests -v
```

Bash 3.2+ runs the launcher. Python 3 runs the installer and offline tests.
ShellCheck is an optional development tool. The test suite uses a fake Codex
executable and makes no model calls. GitHub Actions runs it on Linux and macOS.

## What to preserve

- Fresh worker conversations with only the supplied task context and normal
  Codex/project instructions.
- An immediate ID from `spawn`, readable results, and workers that exit when done.
- Saved model and reasoning settings when steering a worker.
- Explicit worker identity and protection against recursive delegation.
- Literal handling of prompts, including quotes, newlines, and shell syntax.
- Existing user commands and unrelated Codex hooks during installation.

Keep runtime dependencies out of the launcher. Process lifecycle changes need
behavioral tests, especially around stopping, resuming, and concurrent completion.
Use small, bounded prompts if a change needs a real Codex check, and stop any test
workers afterward.

## Pull requests

Describe the behavior being fixed, the resulting behavior, and how you tested it.
Keep unrelated cleanup separate. Update the README when command usage or defaults
change, and add a short entry to the changelog.

When reporting a bug, include your OS, Bash version, Codex CLI version, command,
and the observed error. Share only the relevant log excerpt; job folders can
contain task context and code from your projects.
