"""Offline exit-status coverage for ci-jobs and wait_packaging."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent

JENKINS_STUB = '''\
import os

class Jenkins:
    def __init__(self, *args, **kwargs):
        self.job_calls = 0
        self.build_calls = 0

    def get_job_info(self, job):
        self.job_calls += 1
        number = 41 if self.job_calls == 1 else 42
        return {'lastBuild': {'number': number}, 'lastCompletedBuild': {'number': 42}}

    def build_job(self, job, parameters):
        with open(os.environ['STUB_LOG'], 'a') as log:
            log.write('build %s %r\\n' % (job, parameters))

    def get_build_info(self, job, number):
        self.build_calls += 1
        with open(os.environ['STUB_LOG'], 'a') as log:
            log.write('info %s %s\\n' % (job, number))
        info = {'url': 'https://jenkins.invalid/job/%s/%s/' % (job, number),
                'building': self.build_calls == 1}
        if os.environ['STUB_RESULT'] != 'MISSING':
            info['result'] = None if os.environ['STUB_RESULT'] == 'NULL' else os.environ['STUB_RESULT']
        return info
'''


class CiJobsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        (self.directory / 'jenkins.py').write_text(JENKINS_STUB)
        (self.directory / 'sitecustomize.py').write_text('import time\ntime.sleep = lambda _: None\n')
        gopass = self.directory / 'gopass'
        gopass.write_text('#!/bin/sh\nprintf "placeholder\\nUsername: test\\n"\n')
        gopass.chmod(0o755)
        self.log = self.directory / 'log'
        self.log.touch()

    def run_cli(self, args, result):
        env = os.environ.copy()
        env.update({
            'PATH': f"{self.directory}{os.pathsep}{env.get('PATH', '')}",
            'PYTHONPATH': str(self.directory),
            'STUB_RESULT': result,
            'STUB_LOG': str(self.log),
        })
        return subprocess.run(
            [sys.executable, str(ROOT / 'ci-jobs'), *args],
            env=env, text=True, capture_output=True, timeout=10,
        )

    def test_waited_commands_and_green_report_result(self):
        commands = [
            (['poll', 'some-job'], 'some-job', '41'),
            (['poll', 'some-job', '17'], 'some-job', '17'),
            (['release', 'packages', '3.4.0'], 'release_packages', '42'),
            (['release', 'tarballs', '3.4.0'], 'tarballs-release', '42'),
            (['pipeline', 'foreman', '3.4.0'], 'foreman-3.4-release-pipeline', '42'),
            (['pipeline', 'pulpcore', '3.4.0'], 'pulpcore-3.4-rpm-pipeline', '42'),
            (['green', 'some-job'], 'some-job', '42'),
        ]
        for args, job, number in commands:
            for result in ('SUCCESS', 'FAILURE', 'UNSTABLE', 'ABORTED', 'NULL', 'MISSING', 'OTHER'):
                with self.subTest(args=args, result=result):
                    self.log.write_text('')
                    proc = self.run_cli(args, result)
                    self.assertEqual(proc.returncode, 0 if result == 'SUCCESS' else 1, proc.stderr)
                    output_result = 'None' if result in ('NULL', 'MISSING') else result
                    prefix = f'Checking job {job}\n' if args[0] == 'green' else ''
                    self.assertEqual(proc.stdout, f'{prefix}https://jenkins.invalid/job/{job}/{number}/\n{output_result}\n')
                    self.assertEqual(proc.stderr, '')
                    self.assertEqual(self.log.read_text().count(f'info {job} {number}\n'), 2)

    def test_no_wait_returns_url_without_polling_or_checking_result(self):
        for args, job in (
            (['release', 'packages', '3.4.0', '--no-wait'], 'release_packages'),
            (['pipeline', 'foreman', '3.4.0', '--no-wait'], 'foreman-3.4-release-pipeline'),
        ):
            for result in ('SUCCESS', 'FAILURE', 'UNSTABLE', 'ABORTED', 'NULL', 'MISSING'):
                with self.subTest(args=args, result=result):
                    self.log.write_text('')
                    proc = self.run_cli(args, result)
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(proc.stdout, f'https://jenkins.invalid/job/{job}/42/\n')
                    self.assertEqual(proc.stderr, '')
                    self.assertEqual(self.log.read_text().count(f'info {job} 42\n'), 1)


class WaitPackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        (self.directory / 'wait_packaging').write_bytes((ROOT / 'wait_packaging').read_bytes())
        (self.directory / 'settings').write_text('FOREMAN_VERSION=3.4\n')
        stub = self.directory / 'ci-jobs'
        stub.write_text('''\
#!/bin/bash
printf '%s\\n' "$*" >> "$STUB_DIR/calls"
case "$2" in
  foreman-packaging-deb-*) name=deb; code=$DEB_STATUS ;;
  foreman-packaging-rpm-*) name=rpm; code=$RPM_STATUS ;;
  pulpcore-packaging-rpm-*) name=pulpcore; code=$PULP_STATUS ;;
  *) exit 99 ;;
esac
# A delayed second child proves the parent waits even if the first fails.
if [[ $name == rpm ]]; then sleep 0.2; fi
touch "$STUB_DIR/$name.done"
exit "$code"
''')
        stub.chmod(0o755)

    def run_wait(self, project, deb=0, rpm=0, pulp=0):
        env = os.environ.copy()
        env.update({
            'PROJECT': project, 'VERSION': '5.6', 'STUB_DIR': str(self.directory),
            'DEB_STATUS': str(deb), 'RPM_STATUS': str(rpm), 'PULP_STATUS': str(pulp),
        })
        return subprocess.run(
            ['bash', '-e', str(self.directory / 'wait_packaging')],
            cwd=self.directory, env=env, text=True, capture_output=True, timeout=10,
        )

    def test_parallel_children_all_status_combinations_and_both_reaped(self):
        for deb, rpm in ((0, 0), (0, 7), (9, 0), (9, 7)):
            with self.subTest(deb=deb, rpm=rpm):
                for path in self.directory.glob('*.done'):
                    path.unlink()
                calls = self.directory / 'calls'
                if calls.exists():
                    calls.unlink()
                proc = self.run_wait('foreman', deb, rpm)
                self.assertEqual(proc.returncode == 0, deb == 0 and rpm == 0, proc.stderr)
                self.assertEqual({p.name for p in self.directory.glob('*.done')}, {'deb.done', 'rpm.done'})
                self.assertCountEqual((self.directory / 'calls').read_text().splitlines(), [
                    'poll foreman-packaging-deb-3.4-release',
                    'poll foreman-packaging-rpm-3.4-release',
                ])

    def test_katello_waits_for_foreman_rpm_only(self):
        for status in (0, 6):
            with self.subTest(status=status):
                calls = self.directory / 'calls'
                if calls.exists():
                    calls.unlink()
                proc = self.run_wait('katello', deb=9, rpm=status)
                self.assertEqual(proc.returncode, status, proc.stderr)
                self.assertEqual(calls.read_text(), 'poll foreman-packaging-rpm-3.4-release\n')
                self.assertTrue((self.directory / 'rpm.done').exists())
                self.assertFalse((self.directory / 'deb.done').exists())

    def test_pulpcore_remains_single_synchronous_poll(self):
        for status in (0, 6):
            with self.subTest(status=status):
                calls = self.directory / 'calls'
                if calls.exists():
                    calls.unlink()
                proc = self.run_wait('pulpcore', pulp=status)
                self.assertEqual(proc.returncode, status, proc.stderr)
                self.assertEqual((self.directory / 'calls').read_text(), 'poll pulpcore-packaging-rpm-5.6-release\n')
                self.assertTrue((self.directory / 'pulpcore.done').exists())


if __name__ == '__main__':
    unittest.main()
