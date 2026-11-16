"""Read-only bounded review of reachable Git history; never print matched text."""
from __future__ import annotations

import hashlib
import json
import subprocess

from .review_public_files import SECRET_PATTERNS, path_issue, review_blob


def git(*args):
    return subprocess.run(['git', *args], capture_output=True, check=True, timeout=30).stdout


def audit():
    commits = git('rev-list', '--all').decode('ascii').splitlines()
    if not commits or len(commits) > 1000:
        raise ValueError('History size is outside the review budget')
    seen, findings = set(), []
    total = 0
    for commit in commits:
        message = git('cat-file', 'commit', commit).decode('utf-8', errors='replace')
        for code, pattern in SECRET_PATTERNS.items():
            if pattern.search(message):
                findings.append({'commit': commit, 'code': code, 'scope': 'commit_metadata'})
        for entry in git('ls-tree', '-r', '-z', '-l', commit).split(b'\0'):
            if not entry:
                continue
            metadata, raw_path = entry.split(b'\t', 1)
            mode, kind, oid, size = metadata.decode('ascii').split()
            path = raw_path.decode('utf-8')
            if (path, oid, mode) in seen:
                continue
            seen.add((path, oid, mode))
            # Fingerprint paths so an accidentally committed private filename is
            # not repeated in the audit output. The Git object identifies it.
            location = {'commit': commit, 'blob': oid, 'path_fingerprint': hashlib.sha256(raw_path).hexdigest()}
            issue = path_issue(path)
            if issue or kind != 'blob' or mode not in ('100644', '100755'):
                findings.append({**location, 'code': issue or 'NON_REGULAR_GIT_ENTRY'})
                continue
            size = int(size)
            total += size
            if size > 2 * 1024 * 1024 or total > 64 * 1024 * 1024 or len(seen) > 10000:
                raise ValueError('History exceeds the review byte budget')
            raw = git('cat-file', 'blob', oid)
            for item in review_blob(path, raw, mode):
                findings.append({**location, 'code': item['code'], **({'line': item['line']} if 'line' in item else {})})
    return {'commits_reviewed': len(commits), 'unique_file_versions': len(seen), 'findings': findings,
            'scope': 'Reachable Git history only; signatures and path policy supplement manual review, not complete secret detection.'}


def main():
    try:
        result = audit()
        print(json.dumps(result, indent=2))
        return 1 if result['findings'] else 0
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError):
        print(json.dumps({'error': 'HISTORY_REVIEW_INCOMPLETE', 'message': 'History could not be reviewed within the local safety budget'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
