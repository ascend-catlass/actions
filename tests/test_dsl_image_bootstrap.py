"""Exercise cold, warm and concurrent image creation without a Docker daemon."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('bash') and os.name != 'nt', 'requires Linux bash')
class ImageBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        manifests = self.source / 'python/tla_dsl'
        manifests.mkdir(parents=True)
        (manifests / 'requirements.txt').write_text('pytest\n')
        (manifests / 'pyproject.toml').write_text('[project]\nname="test"\n')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        docker = self.bin / 'docker'
        docker.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys, time
root = pathlib.Path(os.environ['FAKE_DOCKER_STATE'])
args = sys.argv[1:]
if args[:2] == ['image', 'inspect']:
    sys.exit(0 if (root / 'ready').exists() else 1)
assert args[0] == 'build', args
context = pathlib.Path(args[-1])
assert (context / 'Dockerfile').is_file()
assert (context / 'requirements.txt').is_file()
assert (context / 'pyproject.toml').is_file()
with (root / 'builds').open('a') as f:
    f.write(json.dumps(args) + '\\n')
time.sleep(0.2)
(root / 'ready').touch()
''')
        docker.chmod(0o755)
        self.env = {**os.environ, 'PATH': f'{self.bin}:{os.environ["PATH"]}',
                    'RUNNER_TEMP': str(self.root), 'FAKE_DOCKER_STATE': str(self.root)}
        self.command = ['bash', str(ROOT / 'scripts/dsl-env/ensure-image.sh'), str(self.source), 'test:weekly']

    def run_bootstrap(self):
        return subprocess.run(self.command, env=self.env, text=True, capture_output=True)

    def test_missing_image_is_built_immediately(self):
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('is missing', result.stdout)
        builds = (self.root / 'builds').read_text().splitlines()
        self.assertEqual(len(builds), 1)
        self.assertIn('test:weekly', json.loads(builds[0]))

    def test_existing_image_is_reused(self):
        (self.root / 'ready').touch()
        result = self.run_bootstrap()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / 'builds').exists())

    def test_parallel_jobs_build_only_once(self):
        first = subprocess.Popen(self.command, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        second = subprocess.Popen(self.command, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for proc in (first, second):
            out, err = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode, 0, out + err)
        self.assertEqual(len((self.root / 'builds').read_text().splitlines()), 1)


if __name__ == '__main__':
    unittest.main()
