#!/usr/bin/env python3
"""Register the tiny global SessionStart hook. Python is only needed to install."""
import json
import os
from pathlib import Path
import shlex
import shutil

repo = Path(__file__).resolve().parent
codex_dir = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')).expanduser()
codex_dir.mkdir(parents=True, exist_ok=True)
path = codex_dir / 'hooks.json'
data = json.loads(path.read_text()) if path.exists() else {}
groups = data.setdefault('hooks', {}).setdefault('SessionStart', [])
group = {
    'matcher': 'startup|resume|clear|compact',
    'hooks': [{
        'type': 'command',
        'command': 'bash ' + shlex.quote(str(repo / 'mcx')) + ' _context',
        'timeout': 5,
        'statusMessage': 'Loading multi-codex context',
    }],
}
# Replace only our own entry; preserve every unrelated hook.
groups[:] = [entry for entry in groups if not any(
    hook.get('statusMessage') == 'Loading multi-codex context'
    for hook in entry.get('hooks', []))]
groups.append(group)
rendered = json.dumps(data, indent=2) + '\n'
if not path.exists() or path.read_text() != rendered:
    if path.exists():
        shutil.copy2(path, path.with_suffix('.json.mcx-backup'))
    temp = path.with_name(path.name + '.mcx-tmp')
    temp.write_text(rendered)
    temp.chmod(0o600)
    temp.replace(path)
print(f'Registered SessionStart hook in {path}')
print('In Codex, open /hooks and trust the multi-codex hook once.')
print('New sessions will receive coordinator or worker instructions automatically.')
