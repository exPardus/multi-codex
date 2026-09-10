# Context design

The startup hook identifies the role and points to the skill. The skill explains
the workflow. Worker results carry the evidence the parent needs to act.

## What loads when

| Layer | Content | When it enters context |
| --- | --- | --- |
| Skill metadata | Short name and specific trigger description | Skill discovery |
| Startup hook | Launcher, role, default model, recursion boundary | Session start/resume/clear/compaction |
| `skills/mcx/SKILL.md` | Commands, delegation, model choice, result handling | When the skill is selected |
| Worker input | Worker rules plus the parent's explicit task | Every worker launch/resume |
| Worker result | Outcome, file paths, checks/results, blockers | Parent calls `mcx result` |
| Event logs | Full execution details | Read only for diagnosis |

OpenAI documents progressive skill loading: the initial catalog contains names,
descriptions, and paths; full instructions load when selected. Its guidance calls
for concise descriptions with trigger words first because catalog descriptions
can be shortened. Our `mcx` description leads with the tool and supported actions.
See [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills).

Anthropic also loads skill bodies on use. This lets us keep a single shared skill
instead of putting a command manual into every session's startup context.
We use portable `name` and `description` frontmatter; optional Codex appearance
metadata lives separately in `agents/openai.yaml`.
See [Anthropic: Skills](https://code.claude.com/docs/en/skills).

## Small, portable hooks

`mcx _context` reads the worker marker and prints short plain text. Both harnesses
accept plain stdout as SessionStart context. JSON is useful when returning hook
decisions or additional fields, but adds no value to this role-only output.
The hook performs no network requests, model calls, file scans, or job listing.
It runs on every SessionStart source, including Claude's fork source.
See [Anthropic: Hooks](https://code.claude.com/docs/en/hooks).

Both plugin hosts provide `CLAUDE_PLUGIN_ROOT`; Codex documents this compatibility
alias. That gives the shared hook a reliable path after plugin caching. Codex
requires separate hook trust; installation alone does not activate the hook.
We retain the host's context limits and keep our output below 1,000 characters
in tests rather than raising those limits.
See [OpenAI: Hooks](https://learn.chatgpt.com/docs/hooks).

The coordinator hook points to `spawn --wait` / `steer --wait` for harness-managed
background execution. Both role messages stay below 1,000 characters, checked by
the test suite. A cached absolute launcher path adds its own length.

Worker rules also appear in the initial task input. This small intentional
duplication keeps workers correctly identified when a plugin is absent or its
hook has not been trusted. The CLI guard separately rejects worker `spawn` and
`steer` calls. Native Codex subagents remain permitted.

## Useful information, not full transcripts

The parent supplies the task, relevant files or excerpts, constraints, and a
verification target. The worker returns a concise outcome with evidence and
blockers; complete logs stay on disk. The parent reads the final result first and
opens logs when diagnosis requires them. No output is silently truncated by mcx.

This is our implementation choice informed by Anthropic's guidance to manage
context and give agents verifiable success criteria. It reduces irrelevant text;
it does not prove a universal improvement in model accuracy.
See [Anthropic: Best practices](https://code.claude.com/docs/en/best-practices).
