"""Check installation without touching the user's PATH or Codex configuration."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]


class Install(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mcx install ')
        self.root = Path(self.temp.name)
        self.bin = self.root / 'bin'
        self.codex = self.root / 'codex'
        self.env = dict(os.environ, MCX_BIN_DIR=str(self.bin), CODEX_HOME=str(self.codex),
                        PATH=str(self.bin) + os.pathsep + os.environ['PATH'])
        self.env.pop('MCX_WORKER', None)

    def tearDown(self):
        self.temp.cleanup()

    def install(self):
        return subprocess.run([sys.executable, str(REPO / 'install-codex.py')],
                              env=self.env, capture_output=True, text=True, timeout=5)

    def test_aliases_work_from_another_directory_and_install_is_repeatable(self):
        for _ in range(2):
            result = self.install()
            self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('mcx', 'multicodex'):
            self.assertEqual((self.bin / name).resolve(), REPO / 'mcx')
            result = subprocess.run([name, '--help'], cwd=self.root, env=self.env,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('mcx spawn', result.stdout)
        context = subprocess.run(['mcx', '_context'], cwd=self.root, env=self.env,
                                 capture_output=True, text=True, timeout=5)
        self.assertIn('available as: mcx', context.stdout)
        self.assertNotIn(str(REPO), context.stdout)
        data = json.loads((self.codex / 'hooks.json').read_text())
        self.assertEqual(len(data['hooks']['SessionStart']), 1)

    def test_keeps_unrelated_hooks_even_in_the_same_group(self):
        self.codex.mkdir()
        other = {'type': 'command', 'command': 'true'}
        original = {'hooks': {'Stop': [{'hooks': [other]}], 'SessionStart': [
            {'matcher': 'startup', 'hooks': [other, {
                'type': 'command', 'command': 'old mcx path',
                'statusMessage': 'Loading multi-codex context'}]}]}}
        path = self.codex / 'hooks.json'
        path.write_text(json.dumps(original))
        self.assertEqual(self.install().returncode, 0)
        current = json.loads(path.read_text())
        self.assertEqual(current['hooks']['Stop'], original['hooks']['Stop'])
        self.assertEqual(current['hooks']['SessionStart'][0]['hooks'], [other])
        self.assertEqual(json.loads(path.with_suffix('.json.mcx-backup').read_text()), original)

    def test_does_not_replace_an_existing_command(self):
        self.bin.mkdir()
        existing = self.bin / 'mcx'
        existing.write_text('a different program')
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Refusing to replace', result.stderr)
        self.assertEqual(existing.read_text(), 'a different program')
        self.assertFalse((self.codex / 'hooks.json').exists())


if __name__ == '__main__':
    unittest.main()
