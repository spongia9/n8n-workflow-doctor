"""Test the acceptance runner's honesty and safe failure behavior, not Docker."""
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from tools.docker_smoke import CheckFailed, archive, local_engine, main, workflow
import zipfile


class DockerRunnerTests(unittest.TestCase):
    def test_missing_docker_is_not_a_deployment_pass(self):
        out = io.StringIO()
        with patch('tools.docker_smoke.shutil.which', return_value=None), patch('tools.docker_smoke.run') as run, redirect_stdout(out):
            code = main([])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out.getvalue())['state'], 'not_run')
        run.assert_not_called()

    def test_remote_engine_is_rejected_before_context_is_uploaded(self):
        with patch.dict('os.environ', {'DOCKER_HOST': 'ssh://FABRICATED_PRIVATE_HOST'}), patch('tools.docker_smoke.docker') as run:
            with self.assertRaises(CheckFailed) as caught:
                local_engine()
        self.assertNotIn('FABRICATED_PRIVATE_HOST', str(caught.exception))
        run.assert_not_called()

    def test_command_failure_does_not_echo_stderr_or_fake_success(self):
        out = io.StringIO()
        with patch('tools.docker_smoke.shutil.which', return_value='docker'), patch('tools.docker_smoke.local_engine', side_effect=OSError('FABRICATED_PRIVATE_ERROR')), redirect_stdout(out):
            code = main([])
        self.assertEqual(code, 1)
        self.assertNotIn('FABRICATED_PRIVATE_ERROR', out.getvalue())
        self.assertEqual(json.loads(out.getvalue())['state'], 'failed')

    def test_only_fabricated_fixture_bytes_are_generated(self):
        raw = json.dumps(workflow()).encode()
        with zipfile.ZipFile(io.BytesIO(archive([('synthetic.json', raw)]))) as zf:
            self.assertEqual(zf.read('synthetic.json'), raw)


if __name__ == '__main__':
    unittest.main()
