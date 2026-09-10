#!/usr/bin/env python3
"""Install PATH aliases and the global Codex hook. Standard library only."""
import json
import os
from pathlib import Path
import shlex
import shutil

repo = Path(__file__).resolve().parent
codex_dir = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')).expanduser()
bin_dir = Path(os.environ.get('MCX_BIN_DIR', Path.home() / '.local/bin')).expanduser().absolute()
links = [bin_dir / name for name in ('mcx', 'multicodex')]
for link in links:
    if link.exists() or link.is_symlink():
        if not link.is_symlink() or link.resolve() != repo / 'mcx':
            raise SystemExit(f'Refusing to replace {link}; choose a different MCX_BIN_DIR.')
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
# Preserve unrelated handlers even when they share a group with our old hook.
kept = []
for entry in groups:
    handlers = [hook for hook in entry.get('hooks', [])
                if hook.get('statusMessage') != 'Loading multi-codex context']
    if handlers:
        kept.append(dict(entry, hooks=handlers))
groups[:] = kept
groups.append(group)
rendered = json.dumps(data, indent=2) + '\n'
bin_dir.mkdir(parents=True, exist_ok=True)
codex_dir.mkdir(parents=True, exist_ok=True)
for link in links:
    if not link.is_symlink():
        link.symlink_to(repo / 'mcx')
if not path.exists() or path.read_text() != rendered:
    if path.exists():
        shutil.copy2(path, path.with_suffix('.json.mcx-backup'))
    temp = path.with_name(path.name + '.mcx-tmp')
    temp.write_text(rendered)
    temp.chmod(0o600)
    temp.replace(path)
print(f'Installed mcx and multicodex in {bin_dir}')
if str(bin_dir) not in os.environ.get('PATH', '').split(os.pathsep):
    print('Add this directory to your shell PATH:')
    print(f'  export PATH={shlex.quote(str(bin_dir))}:"$PATH"')
print(f'Registered SessionStart hook in {path}')
print('In Codex, open /hooks and trust the multi-codex hook once.')
print('New sessions will receive coordinator or worker instructions automatically.')
