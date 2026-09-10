"""Check installation with fake app CLIs and isolated user configuration."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / 'plugins/multi-codex'


class Install(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mcx install ')
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.codex = self.root / 'codex'
        self.apps = self.root / 'apps'
        self.apps.mkdir()
        self.calls = self.root / 'calls'
        for host in ('codex', 'claude'):
            executable = self.apps / host
            executable.write_text(f'#!{sys.executable}\n' + '''import json, os, sys
from pathlib import Path
with open(os.environ['MCX_TEST_CALLS'], 'a') as log:
    log.write(json.dumps([Path(sys.argv[0]).name] + sys.argv[1:]) + '\\n')
if os.environ.get('MCX_TEST_FAIL') and sys.argv[2] in ('add', 'install'):
    sys.exit(1)
''')
            executable.chmod(0o755)
        self.env = dict(os.environ, MCX_BIN_DIR=str(self.bin), CODEX_HOME=str(self.codex),
                        MCX_TEST_CALLS=str(self.calls),
                        PATH=os.pathsep.join((str(self.apps), str(self.bin), os.environ['PATH'])))
        self.env.pop('MCX_WORKER', None)

    def tearDown(self):
        self.temp.cleanup()

    def install(self, *args):
        return subprocess.run([sys.executable, str(REPO / 'install.py'), *args],
                              env=self.env, capture_output=True, text=True, timeout=5)

    def test_aliases_work_from_another_directory_and_install_is_repeatable(self):
        for _ in range(2):
            result = self.install()
            self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('mcx', 'multicodex'):
            self.assertEqual((self.bin / name).resolve(), (REPO / 'mcx').resolve())
            result = subprocess.run([name, '--help'], cwd=self.root, env=self.env,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('mcx spawn', result.stdout)
        context = subprocess.run(['mcx', '_context'], cwd=self.root, env=self.env,
                                 capture_output=True, text=True, timeout=5)
        self.assertIn('available as: mcx', context.stdout)
        self.assertNotIn(str(REPO), context.stdout)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertIn(['codex', 'plugin', 'add', 'multi-codex@multi-codex'], calls)
        self.assertIn(['claude', 'plugin', 'install', 'multi-codex@multi-codex', '--scope', 'user'], calls)
        self.assertFalse((self.codex / 'hooks.json').exists())

    def legacy_hooks(self):
        self.codex.mkdir()
        other = {'type': 'command', 'command': 'true'}
        original = {'hooks': {'Stop': [{'hooks': [other]}], 'SessionStart': [
            {'matcher': 'startup', 'hooks': [other, {
                'type': 'command', 'command': 'old mcx path',
                'statusMessage': 'Loading multi-codex context'}]}]}}
        path = self.codex / 'hooks.json'
        path.write_text(json.dumps(original))
        return path, original, other

    def test_migrates_only_our_old_hook_after_install(self):
        path, original, other = self.legacy_hooks()
        self.assertEqual(self.install('codex').returncode, 0)
        current = json.loads(path.read_text())
        self.assertEqual(current['hooks']['Stop'], original['hooks']['Stop'])
        self.assertEqual(current['hooks']['SessionStart'][0]['hooks'], [other])
        self.assertEqual(json.loads(path.with_suffix('.json.mcx-backup').read_text()), original)
        self.assertEqual(self.install('codex').returncode, 0)
        self.assertEqual(json.loads(path.with_suffix('.json.mcx-backup').read_text()), original)

    def test_failed_install_preserves_old_hook(self):
        path, original, _ = self.legacy_hooks()
        self.env['MCX_TEST_FAIL'] = '1'
        result = self.install('codex')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(path.read_text()), original)
        self.assertFalse(path.with_suffix('.json.mcx-backup').exists())

    def test_cli_only_does_not_change_app_config(self):
        self.assertEqual(self.install('cli').returncode, 0)
        self.assertFalse(self.calls.exists())
        self.assertFalse(self.codex.exists())

    def test_does_not_replace_an_existing_command(self):
        self.bin.mkdir()
        existing = self.bin / 'mcx'
        existing.write_text('a different program')
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Refusing to replace', result.stderr)
        self.assertEqual(existing.read_text(), 'a different program')
        self.assertFalse(self.calls.exists())

    def test_hook_survives_plugin_cache_relocation_without_path_install(self):
        cached = self.root / 'cached plugin'
        shutil.copytree(PLUGIN, cached)
        hook = json.loads((cached / 'hooks/hooks.json').read_text())['hooks']['SessionStart'][0]['hooks'][0]
        for role in ('0', '1'):
            env = dict(self.env, CLAUDE_PLUGIN_ROOT=str(cached), MCX_WORKER=role, PATH='/usr/bin:/bin')
            result = subprocess.run(['bash', '-c', hook['command']], cwd=self.root, env=env,
                                    input='{"source":"startup"}', text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertLess(len(result.stdout), 1000)
            if role == '0':
                self.assertIn(str(cached / 'mcx'), result.stdout)
                self.assertNotIn(str(REPO), result.stdout)
            else:
                self.assertIn('MCX_WORKER=1', result.stdout)
                self.assertIn('WORKER', result.stdout)


if __name__ == '__main__':
    unittest.main()
