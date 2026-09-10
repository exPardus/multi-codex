#!/usr/bin/env python3
"""Install mcx commands and native plugins. Python standard library; no daemon."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess

REPO = Path(__file__).resolve().parent


def remove_legacy_hook():
    """The plugin now owns this hook; retain every unrelated user handler."""
    codex_dir = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')).expanduser()
    path = codex_dir / 'hooks.json'
    if not path.exists():
        return
    original = path.read_text()
    data = json.loads(original)
    groups = data.get('hooks', {}).get('SessionStart', [])
    kept = []
    changed = False
    for entry in groups:
        handlers = [hook for hook in entry.get('hooks', [])
                    if hook.get('statusMessage') != 'Loading multi-codex context']
        if len(handlers) == len(entry.get('hooks', [])):
            kept.append(entry)
        else:
            changed = True
            if handlers:
                kept.append(dict(entry, hooks=handlers))
    if changed:
        groups[:] = kept
        shutil.copy2(path, path.with_suffix('.json.mcx-backup'))
        temp = path.with_name(path.name + '.mcx-tmp')
        temp.write_text(json.dumps(data, indent=2) + '\n')
        temp.chmod(0o600)
        temp.replace(path)
        print(f'Migrated the old startup hook to the plugin; backup: {path}.mcx-backup')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', nargs='?', default='both',
                        choices=('both', 'codex', 'claude', 'cli'),
                        help='what to install (default: both apps and PATH commands)')
    target = parser.parse_args(argv).target
    hosts = ('codex', 'claude') if target == 'both' else (() if target == 'cli' else (target,))
    bin_dir = Path(os.environ.get('MCX_BIN_DIR', Path.home() / '.local/bin')).expanduser().absolute()
    links = [bin_dir / name for name in ('mcx', 'multicodex')]
    for link in links:
        if link.exists() or link.is_symlink():
            if not link.is_symlink() or link.resolve() != (REPO / 'mcx').resolve():
                parser.error(f'Refusing to replace {link}; choose a different MCX_BIN_DIR.')
    for host in hosts:
        if not shutil.which(host):
            parser.error(f'{host} is not on PATH; install it first, or select a different target.')
    try:
        bin_dir.mkdir(parents=True, exist_ok=True)
        for link in links:
            if not link.is_symlink():
                link.symlink_to(REPO / 'mcx')
        print(f'Installed mcx and multicodex in {bin_dir}', flush=True)
        for host in hosts:
            subprocess.run([host, 'plugin', 'marketplace', 'add', str(REPO)], check=True)
            action = 'add' if host == 'codex' else 'install'
            command = [host, 'plugin', action, 'multi-codex@multi-codex']
            if host == 'claude':
                command += ['--scope', 'user']
            subprocess.run(command, check=True)
            if host == 'codex':
                remove_legacy_hook()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Installation stopped: {error}\nFix the error and rerun; completed steps are safe to repeat.\n')
    if str(bin_dir) not in os.environ.get('PATH', '').split(os.pathsep):
        print('Add this directory to your shell PATH:')
        print(f'  export PATH={shlex.quote(str(bin_dir))}:"$PATH"')
    if 'codex' in hosts:
        print('In Codex, open /hooks and trust the multi-codex SessionStart hook once.')
    if hosts:
        print('Start new sessions to load the mcx skill and automatic startup context.')


if __name__ == '__main__':
    main()
