"""Offline tests for Foreman/Katello version pairing in branch_project."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent


class BranchProjectPairingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copy(ROOT / 'branch_project', self.root / 'branch_project')
        shutil.copy(ROOT / 'settings', self.root / 'settings')
        (self.root / 'releases/foreman/3.16').mkdir(parents=True)
        (self.root / 'releases/candlepin/3.16').mkdir(parents=True)
        self.checkouts = self.root / 'checkouts'
        foreman = self.checkouts / 'foreman'
        (foreman / '.github/workflows').mkdir(parents=True)
        self.workflow = foreman / '.github/workflows/foreman.yml'
        self.workflow.write_text('steps:\n  - plugin_repository: katello\n    another_key: value\n')
        self.packit = foreman / '.packit.yaml'
        self.packit.write_text('job: nightly\nurl: /rpm/develop\n')
        candlepin = self.checkouts / 'candlepin-packaging'
        (candlepin / 'repoclosure').mkdir(parents=True)
        (candlepin / 'package_manifest.yaml').write_text("candlepin_version: 'old'\n")
        (candlepin / 'repoclosure/yum.conf').write_text(
            'candlepin-nightly-staging /candlepin/nightly/ Candlepin nightly staging\n'
        )
        ensure = self.root / 'ensure_clean_git_checkouts'
        ensure.write_text('#!/bin/bash\nprintf "ensure %s\\n" "$*" >> "$TEST_LOG"\nprintf "%s\\n" "$@"\n')
        ensure.chmod(0o755)
        bindir = self.root / 'bin'
        bindir.mkdir()
        git = bindir / 'git'
        git.write_text('#!/bin/bash\nprintf "git %s\\n" "$*" >> "$TEST_LOG"\n')
        git.chmod(0o755)
        self.log = self.root / 'calls'
        self.env = os.environ.copy()
        for key in ('KATELLO_VERSION', 'FULLGPGKEY', 'GIT_REMOTE'):
            self.env.pop(key, None)
        self.env.update({
            'PATH': str(bindir) + os.pathsep + self.env.get('PATH', ''),
            'GIT_DIR': str(self.checkouts),
            'PROJECT': 'foreman',
            'VERSION': '3.16',
            'FOREMAN_VERSION': 'none',
            'TEST_LOG': str(self.log),
        })

    def run_branch(self, repo, **env):
        return subprocess.run(
            ['bash', '-e', str(self.root / 'branch_project'), repo],
            cwd=self.root, env={**self.env, **env}, capture_output=True,
            text=True, timeout=10,
        )

    def test_foreman_pins_katello_pair_and_foreman_branch_and_packit(self):
        result = self.run_branch('foreman', KATELLO_VERSION='4.18')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertEqual(self.workflow.read_text(),
                         'steps:\n  - plugin_repository: katello\n      plugin_version: KATELLO-4.18\n    another_key: value\n')
        self.assertEqual(self.packit.read_text(), 'job: 3.16\nurl: /rpm/3.16\n')
        self.assertEqual(self.log.read_text().splitlines(), [
            'ensure foreman',
            'git fetch --quiet upstream',
            'git checkout -b 3.16-stable upstream/develop',
            'git add .github/workflows/foreman.yml .packit.yaml',
            'git commit --message Pin CI to 3.16 stable branches',
        ])

    def test_missing_or_invalid_pair_fails_before_ensure_or_git(self):
        for value in (None, '', '4', '4.', '.18', '4.18.0', 'v4.18', '4.x', '4.18\n', ' 4.18'):
            with self.subTest(value=value):
                env = {} if value is None else {'KATELLO_VERSION': value}
                before_workflow = self.workflow.read_text()
                before_packit = self.packit.read_text()
                result = self.run_branch('foreman', **env)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('KATELLO_VERSION', result.stderr)
                self.assertIn('X.Y', result.stderr)
                self.assertFalse(self.log.exists(), 'checkout helper or git was invoked')
                self.assertEqual(self.workflow.read_text(), before_workflow)
                self.assertEqual(self.packit.read_text(), before_packit)

    def test_other_project_does_not_require_pair_and_retains_candlepin_behavior(self):
        result = self.run_branch('candlepin-packaging', PROJECT='candlepin')
        self.assertEqual(result.returncode, 0, result.stderr)
        candlepin = self.checkouts / 'candlepin-packaging'
        self.assertEqual((candlepin / 'package_manifest.yaml').read_text(), "candlepin_version: '3.16'\n")
        self.assertEqual((candlepin / 'repoclosure/yum.conf').read_text(),
                         'candlepin-3.16-staging /candlepin/3.16/ Candlepin 3.16 staging\n')
        self.assertEqual(self.log.read_text().splitlines(), [
            'ensure candlepin-packaging',
            'git fetch --quiet upstream',
            'git checkout -b 3.16-stable upstream/develop',
            'git add package_manifest.yaml repoclosure/yum.conf',
            'git commit --message Set Candlepin version to 3.16',
        ])

    def test_other_project_explicit_foreman_checkout_keeps_old_pin(self):
        result = self.run_branch('foreman', PROJECT='candlepin', KATELLO_VERSION='not-a-version')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('plugin_version: KATELLO-3.16', self.workflow.read_text())
        self.assertEqual(self.packit.read_text(), 'job: 3.16\nurl: /rpm/3.16\n')


if __name__ == '__main__':
    unittest.main()
