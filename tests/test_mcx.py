"""Offline end-to-end tests. Run: python3 -m unittest discover -s tests -v"""
import concurrent.futures
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
MCX = REPO / 'mcx'


class Workers(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mcx test ')
        self.cwd = Path(self.temp.name)
        self.jobs = self.cwd / 'state with spaces'
        self.env = dict(os.environ, CODEX_BIN=str(REPO / 'tests/fake-codex'),
                        MCX_DIR=str(self.jobs), CODEX_THREAD_ID='parent-context',
                        XDG_CONFIG_HOME=str(self.cwd / 'global config'))
        for key in ('MCX_MODEL', 'MCX_EFFORT', 'MCX_WORKER', 'MCX_APPROVAL'):
            self.env.pop(key, None)

    def tearDown(self):
        for job in self.jobs.glob('*'):
            if job.is_dir():
                self.run_mcx('stop', job.name)
        self.temp.cleanup()

    def run_mcx(self, *args, input=None, env=None):
        return subprocess.run([str(MCX), *args], cwd=self.cwd, env=env or self.env,
                              input=input, text=True, capture_output=True, timeout=8)

    def spawn(self, prompt='hello', *flags):
        result = self.run_mcx('spawn', *flags, prompt)
        self.assertEqual(result.returncode, 0, result.stderr)
        worker = result.stdout.strip()
        self.assertRegex(worker, r'^[a-zA-Z0-9]{8}$')
        return worker

    def start_waiter(self, *args):
        process = subprocess.Popen([str(MCX), *args], cwd=self.cwd, env=self.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        self.addCleanup(self.close_waiter, process)
        self.assertTrue(select.select([process.stdout], [], [], 5)[0], 'no immediate worker ID')
        worker = process.stdout.readline().strip()
        self.assertRegex(worker, r'^[a-zA-Z0-9]{8}$')
        return process, worker

    @staticmethod
    def close_waiter(process):
        if process.poll() is None:
            process.terminate()
        process.communicate(timeout=8)

    def invocation(self, worker):
        return json.loads(self.await_file(worker, 'invocation.json').read_text())

    def await_file(self, worker, name):
        target = self.jobs / worker / name
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if target.exists() and target.stat().st_size:
                return target
            time.sleep(.03)
        self.fail(f'missing {target}: {self.run_mcx("list").stdout}')

    def await_result(self, worker):
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            result = self.run_mcx('result', worker)
            if result.returncode != 2:
                return result
            time.sleep(.03)
        self.fail('worker did not finish')

    def test_detaches_and_finishes(self):
        start = time.monotonic()
        worker = self.spawn('delay:1')
        self.assertLess(time.monotonic() - start, .8)
        self.assertEqual(self.run_mcx('result', worker).returncode, 2)
        result = self.await_result(worker)
        self.assertEqual((result.returncode, result.stdout), (0, 'delay:1\n'))
        pid = int((self.jobs / worker / 'pid').read_text())
        self.assertFalse(self.process_running(pid))

    def test_fresh_context_model_and_recursion_policy(self):
        worker = self.spawn()
        self.assertEqual(self.await_result(worker).returncode, 0)
        record = json.loads(self.await_file(worker, 'invocation.json').read_text())
        self.assertNotIn('resume', record['args'])
        self.assertIsNone(record['thread'])
        self.assertEqual(record['worker'], '1')
        self.assertIn('You are an mcx WORKER', record['prompt'])
        self.assertIn('gpt-5.6-luna', record['args'])
        self.assertIn('model_reasoning_effort="medium"', record['args'])
        self.assertIn('agents.enabled=true', record['args'])
        self.assertIn(('--enable', 'multi_agent'), list(zip(record['args'], record['args'][1:])))
        self.assertNotIn('--disable', record['args'])
        self.assertIn('agents.default_subagent_model=gpt-5.6-luna', record['args'])
        self.assertIn('agents.default_subagent_reasoning_effort=medium', record['args'])
        self.assertIn('shell_environment_policy.set.MCX_WORKER="1"', record['args'])
        self.assertEqual(record['args'][record['args'].index('-a') + 1], 'never')
        self.assertIn('workspace-write', record['args'])

    def test_wait_prints_id_immediately_and_waits_for_exit(self):
        process, worker = self.start_waiter('spawn', '--wait', 'delay:.5')
        self.assertIsNone(process.poll())
        stdout, stderr = process.communicate(timeout=8)
        self.assertEqual((process.returncode, stdout), (0, ''), stderr)
        self.assertIn('done (exit 0)', stderr)
        self.assertEqual(self.run_mcx('result', worker).stdout, 'delay:.5\n')

    def test_wait_returns_worker_failure(self):
        process, worker = self.start_waiter('spawn', '--wait', 'fail')
        _, stderr = process.communicate(timeout=8)
        self.assertEqual(process.returncode, 7, stderr)
        self.assertIn('failed (exit 7)', stderr)
        self.assertEqual(self.run_mcx('result', worker).returncode, 1)

    def test_wait_cancellation_stops_process_tree(self):
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            with self.subTest(signal=sig):
                process, worker = self.start_waiter('spawn', '--wait', 'hold')
                child = int(self.await_file(worker, 'child-pid').read_text())
                process.send_signal(sig)
                process.communicate(timeout=8)
                self.assertEqual(process.returncode, 128 + sig)
                self.assertFalse(self.process_running(child))
                self.assertIn('stopped', self.run_mcx('list').stdout)

    def test_stop_releases_waiter(self):
        process, worker = self.start_waiter('spawn', '--wait', 'hold')
        self.await_file(worker, 'child-pid')
        self.assertEqual(self.run_mcx('stop', worker).returncode, 0)
        _, stderr = process.communicate(timeout=8)
        self.assertIn(process.returncode, (137, 143), stderr)
        self.assertIn('interrupted', stderr)

    def test_steer_wait_replaces_waiter_and_releases_lock(self):
        first, worker = self.start_waiter('spawn', '--wait', 'hold')
        self.await_file(worker, 'child-pid')
        session = self.invocation(worker)['session']
        second, resumed = self.start_waiter('steer', '--wait', worker, 'hold')
        self.assertEqual(worker, resumed)
        first.communicate(timeout=8)
        self.assertIn(first.returncode, (137, 143))
        self.assertIsNone(second.poll())
        self.await_file(worker, 'events.jsonl')
        self.assertEqual(self.invocation(worker)['session'], session)
        # A second controller can interrupt while steer --wait is still waiting.
        third, resumed = self.start_waiter('steer', '--wait', worker, 'last run')
        second.communicate(timeout=8)
        self.assertIn(second.returncode, (137, 143))
        _, stderr = third.communicate(timeout=8)
        self.assertEqual(third.returncode, 0, stderr)
        self.assertEqual(self.run_mcx('result', resumed).stdout, 'last run\n')

    def test_cancelling_old_waiter_cannot_kill_replacement(self):
        first, worker = self.start_waiter('spawn', '--wait', 'hold')
        self.await_file(worker, 'child-pid')
        first.send_signal(signal.SIGSTOP)
        try:
            self.assertEqual(self.run_mcx('steer', worker, 'hold').returncode, 0)
            self.await_file(worker, 'events.jsonl')
            first.send_signal(signal.SIGTERM)
        finally:
            first.send_signal(signal.SIGCONT)
        first.communicate(timeout=8)
        self.assertEqual(first.returncode, 143)
        self.assertEqual(self.run_mcx('result', worker).returncode, 2)
        self.assertTrue(self.process_running(int((self.jobs / worker / 'pid').read_text())))

    def test_steer_wait_completed_worker(self):
        worker = self.spawn()
        self.await_result(worker)
        process, resumed = self.start_waiter('steer', '--wait', worker, 'follow up')
        _, stderr = process.communicate(timeout=8)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual(self.run_mcx('result', resumed).stdout, 'follow up\n')

    def test_approval_config_precedence_and_steer_preservation(self):
        config = Path(self.env['XDG_CONFIG_HOME']) / 'mcx/config'
        config.parent.mkdir(parents=True)
        config.write_text('# Global preference\n approval = auto # comment\n')
        worker = self.spawn()
        self.await_result(worker)
        args = self.invocation(worker)['args']
        self.assertEqual(args[args.index('-a') + 1], 'on-request')
        self.assertIn('approvals_reviewer=auto_review', args)
        self.assertIn('workspace-write', args)
        (self.jobs / 'config').write_text('approval=never')
        local = self.spawn()
        self.await_result(local)
        self.assertEqual((self.jobs / local / 'approval').read_text().strip(), 'never')
        self.env['MCX_APPROVAL'] = 'unrestricted'
        override = self.spawn()
        self.await_result(override)
        args = self.invocation(override)['args']
        self.assertIn('--dangerously-bypass-approvals-and-sandbox', args)
        self.assertNotIn('--sandbox', args)
        self.assertNotIn('-a', args)
        self.assertEqual((self.jobs / override / 'approval').read_text().strip(), 'unrestricted')
        self.assertEqual(self.run_mcx('steer', worker, 'follow up').returncode, 0)
        self.await_result(worker)
        self.assertIn('approvals_reviewer=auto_review', self.invocation(worker)['args'])

    def test_legacy_jobs_keep_never_on_steer(self):
        worker = self.spawn()
        self.await_result(worker)
        (self.jobs / worker / 'approval').unlink()
        self.env['MCX_APPROVAL'] = 'auto'
        self.assertEqual(self.run_mcx('steer', worker, 'follow up').returncode, 0)
        self.await_result(worker)
        args = self.invocation(worker)['args']
        self.assertEqual(args[args.index('-a') + 1], 'never')

    def test_config_is_validated_and_never_executed(self):
        self.jobs.mkdir()
        for content in ('approval=typo', 'approval=$(touch SHOULD_NOT_EXIST)',
                        'touch SHOULD_NOT_EXIST', 'unknown=auto'):
            with self.subTest(content=content):
                (self.jobs / 'config').write_text(content)
                result = self.run_mcx('spawn', 'hello')
                self.assertEqual(result.returncode, 1)
                self.assertIn('invalid config', result.stderr)
                self.assertFalse((self.cwd / 'SHOULD_NOT_EXIST').exists())
        (self.jobs / 'config').unlink()
        self.env['MCX_APPROVAL'] = 'typo'
        result = self.run_mcx('spawn', 'hello')
        self.assertEqual(result.returncode, 1)
        self.assertIn('invalid MCX_APPROVAL', result.stderr)

    def test_steer_preserves_session_and_model(self):
        worker = self.spawn('hold', '-m', 'gpt-5.6-terra', '-r', 'low')
        self.await_file(worker, 'child-pid')
        before = json.loads(self.await_file(worker, 'invocation.json').read_text())
        child = int((self.jobs / worker / 'child-pid').read_text())
        result = self.run_mcx('steer', worker, 'new direction')
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.await_result(worker)
        self.assertEqual((result.returncode, result.stdout), (0, 'new direction\n'), result.stderr)
        after = json.loads((self.jobs / worker / 'invocation.json').read_text())
        self.assertEqual(before['session'], after['session'])
        self.assertIn('resume', after['args'])
        self.assertIn('gpt-5.6-terra', after['args'])
        self.assertIn('model_reasoning_effort="low"', after['args'])
        self.assertIn('agents.enabled=true', after['args'])
        self.assertIn('agents.default_subagent_model=gpt-5.6-terra', after['args'])
        self.assertIn('agents.default_subagent_reasoning_effort=low', after['args'])
        self.assertFalse(self.process_running(child))

    def test_steer_completed_worker(self):
        worker = self.spawn()
        self.await_result(worker)
        self.assertEqual(self.run_mcx('steer', worker, '-', input='follow up').returncode, 0)
        self.assertEqual(self.await_result(worker).stdout, 'follow up\n')

    @staticmethod
    def process_running(pid):
        check = subprocess.run(['ps', '-p', str(pid), '-o', 'stat='],
                               capture_output=True, text=True)
        return check.returncode == 0 and not check.stdout.strip().startswith('Z')

    def test_stop_removes_process_tree(self):
        worker = self.spawn('hold')
        child = int(self.await_file(worker, 'child-pid').read_text())
        result = self.run_mcx('stop', worker)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('stopped', result.stdout)
        self.assertFalse(self.process_running(child))
        self.assertEqual(self.run_mcx('result', worker).returncode, 1)
        self.assertEqual(self.run_mcx('stop', worker).returncode, 0)

    def test_failure_is_not_an_empty_success(self):
        worker = self.spawn('fail')
        result = self.await_result(worker)
        self.assertEqual(result.returncode, 1)
        self.assertIn('failed', result.stderr)
        self.assertEqual((self.jobs / worker / 'exit-code').read_text().strip(), '7')

    def test_more_than_four_parallel_workers(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            workers = list(pool.map(self.spawn, ['delay:.4'] * 6))
        self.assertEqual(len(set(workers)), 6)
        for worker in workers:
            self.assertEqual(self.await_result(worker).returncode, 0)
        listing = self.run_mcx('list').stdout
        self.assertEqual(len(listing.splitlines()), 7)
        self.assertIn('gpt-5.6-luna', listing)

    def test_literal_stdin_and_paths_with_spaces(self):
        prompt = "Quotes ' \"; $(touch SHOULD_NOT_EXIST) `touch ALSO_NOT`\nsecond line"
        result = self.run_mcx('spawn', '-', input=prompt)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.await_result(result.stdout.strip()).stdout, prompt + '\n')
        self.assertFalse((self.cwd / 'SHOULD_NOT_EXIST').exists())
        self.assertFalse((self.cwd / 'ALSO_NOT').exists())

    def test_workers_cannot_launch_or_steer(self):
        env = dict(self.env, MCX_WORKER='1')
        for args in [('spawn', 'nested'), ('steer', 'abcdefgh', 'nested')]:
            result = self.run_mcx(*args, env=env)
            self.assertEqual(result.returncode, 1)
            self.assertIn('workers cannot', result.stderr)
        self.assertFalse(self.jobs.exists())

    def test_context_hook_separates_roles(self):
        normal = self.run_mcx('_context')
        worker = self.run_mcx('_context', env=dict(self.env, MCX_WORKER='1'))
        self.assertIn('multi-codex helper is available as:', normal.stdout)
        self.assertIn('gpt-5.6-luna/medium', normal.stdout)
        self.assertIn('WORKER, not a coordinator', worker.stdout)
        self.assertIn('may spawn native Codex subagents', worker.stdout)
        self.assertIn('Do not launch independent workers', worker.stdout)
        self.assertIn('Your subagents must follow the same restriction', worker.stdout)
        self.assertNotIn('gpt-5.6-luna/medium', worker.stdout)
        self.assertLess(len(normal.stdout), 1000)
        self.assertLess(len(worker.stdout), 1000)

    def test_stale_pid_does_not_kill_unrelated_process(self):
        worker = self.spawn()
        self.await_result(worker)
        other = subprocess.Popen(['sleep', '10'], start_new_session=True)
        try:
            (self.jobs / worker / 'pid').write_text(str(other.pid))
            (self.jobs / worker / 'state').write_text('running\n')
            self.assertIn('lost', self.run_mcx('stop', worker).stdout)
            self.assertIsNone(other.poll())
        finally:
            other.terminate()
            other.wait()

    def test_denied_process_inspection_is_not_reported_as_dead(self):
        worker = self.spawn('hold')
        self.await_file(worker, 'child-pid')
        bindir = self.cwd / 'restricted-bin'
        bindir.mkdir()
        stub = bindir / 'ps'
        stub.write_text('#!/bin/sh\necho "Operation not permitted" >&2\nexit 126\n')
        stub.chmod(0o755)
        env = dict(self.env, PATH=str(bindir) + os.pathsep + self.env['PATH'])
        self.assertIn('running', self.run_mcx('list', env=env).stdout)
        for args in [('stop', worker), ('steer', worker, 'changed')]:
            result = self.run_mcx(*args, env=env)
            self.assertEqual(result.returncode, 1)
            self.assertIn('inspection denied', result.stderr)

    def test_wait_reports_denied_cancellation(self):
        bindir = self.cwd / 'restricted-bin'
        bindir.mkdir()
        stub = bindir / 'ps'
        stub.write_text('#!/bin/sh\necho "Operation not permitted" >&2\nexit 126\n')
        stub.chmod(0o755)
        original = self.env['PATH']
        self.env['PATH'] = str(bindir) + os.pathsep + original
        try:
            process, worker = self.start_waiter('spawn', '--wait', 'hold')
            self.await_file(worker, 'child-pid')
            process.terminate()
            _, stderr = process.communicate(timeout=8)
            self.assertEqual(process.returncode, 143)
            self.assertIn('cancellation inspection denied', stderr)
        finally:
            self.env['PATH'] = original
        self.assertEqual(self.run_mcx('stop', worker).returncode, 0)

    def test_result_when_worker_finishes_during_process_inspection(self):
        worker = self.spawn()
        self.await_result(worker)
        state = self.jobs / worker / 'state'
        state.write_text('running\n')
        bindir = self.cwd / 'racing-bin'
        bindir.mkdir()
        stub = bindir / 'ps'
        stub.write_text('#!/bin/sh\nprintf "done\\n" > "$MCX_TEST_STATE"\nexit 1\n')
        stub.chmod(0o755)
        env = dict(self.env, PATH=str(bindir) + os.pathsep + self.env['PATH'],
                   MCX_TEST_STATE=str(state))
        result = self.run_mcx('result', worker, env=env)
        self.assertEqual((result.returncode, result.stdout), (0, 'hello\n'), result.stderr)

    def test_invalid_input(self):
        for args in [('spawn', ''), ('spawn', '-m'), ('spawn', '-r', 'ultra', 'task'),
                     ('result', '../..'), ('stop', 'abcdefgh'), ('unknown',)]:
            self.assertEqual(self.run_mcx(*args).returncode, 1, args)


if __name__ == '__main__':
    unittest.main()
