"""History review is bounded, read-only and does not disclose found material."""
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from tools.review_history import audit, main


def fixture_git(*args):
    if args[0] == 'rev-list':
        return b'abc123\n'
    if args[:2] == ('cat-file', 'commit'):
        return b'author fabricated\n\nSynthetic commit\n'
    if args[0] == 'ls-tree':
        return b'100644 blob abcdef 5\tdocs/synthetic.md\0'
    if args[:2] == ('cat-file', 'blob'):
        return b'hello'
    raise AssertionError('Unexpected Git operation')


class HistoryReviewTests(unittest.TestCase):
    @patch('tools.review_history.git', side_effect=fixture_git)
    def test_known_public_history_is_reviewed_without_mutating_git(self, run):
        result = audit()
        self.assertEqual(result['findings'], [])
        self.assertEqual(result['commits_reviewed'], 1)
        self.assertTrue(all(c.args[0] in ('rev-list', 'cat-file', 'ls-tree') for c in run.call_args_list))

    def test_secret_is_reported_by_code_and_object_without_value(self):
        marker = 'ghp_' + 'x' * 36
        def git(*args):
            return marker.encode() if args[:2] == ('cat-file', 'blob') else fixture_git(*args)
        with patch('tools.review_history.git', side_effect=git):
            result = audit()
        self.assertEqual(result['findings'][0]['code'], 'GITHUB_TOKEN')
        self.assertNotIn(marker, json.dumps(result))

    def test_private_path_is_fingerprinted_not_echoed(self):
        def git(*args):
            return b'100644 blob abcdef 5\tprivate/FABRICATED_PRIVATE_NAME.env\0' if args[0] == 'ls-tree' else fixture_git(*args)
        with patch('tools.review_history.git', side_effect=git):
            result = audit()
        self.assertEqual(result['findings'][0]['code'], 'PRIVATE_PATH')
        self.assertNotIn('FABRICATED_PRIVATE_NAME', json.dumps(result))

    def test_failed_review_is_not_success_and_error_text_is_sanitized(self):
        output = io.StringIO()
        with patch('tools.review_history.git', side_effect=OSError('FABRICATED_PRIVATE_ERROR')), redirect_stdout(output):
            code = main()
        self.assertEqual(code, 2)
        self.assertNotIn('FABRICATED_PRIVATE_ERROR', output.getvalue())

    def test_empty_or_oversized_history_fails_closed(self):
        for value in (b'', b'x\n' * 1001):
            with self.subTest(size=len(value)), patch('tools.review_history.git', return_value=value):
                with self.assertRaises(ValueError):
                    audit()
