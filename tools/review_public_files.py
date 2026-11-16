"""Review staged public files locally, reporting locations without secret values.

This guard is deliberately conservative and supplements human review. It never
contacts a service, reads ignored/private input files, or changes the Git index.
"""
from __future__ import annotations

import json
import hashlib
import re
import subprocess
from pathlib import PurePosixPath


PUBLIC_JSON = {
    "tests/fixtures/valid.json", "tests/fixtures/missing_target.json",
    "tests/fixtures/invalid.json", "tests/fixtures/duplicate_id.json",
    "tests/fixtures_compat/synthetic_export_shape.json",
    "examples/sprint2/workflows/A.json", "examples/sprint2/workflows/B.json",
    "examples/sprint2/workflows/C.json", "examples/sprint2/workflows/ERROR_HANDLER.json",
    "examples/sprint2/migration-report.json", "examples/sprint2/dependency-graphs.json",
    "examples/sprint2-formal/workflows/A.json", "examples/sprint2-formal/workflows/B.json",
    "examples/sprint2-formal/workflows/C.json", "examples/sprint2-formal/workflows/ERROR_HANDLER.json",
    "examples/sprint2-formal/migration-report.json", "examples/sprint2-formal/dependency-graphs.json",
    "examples/sprint3/migration-report.json",
}
PUBLIC_HTML = {"examples/sprint3/migration-report.html", "examples/sprint3/structural-report.html"}
PUBLIC_FRONTEND_CONFIG = {"frontend/package.json", "frontend/package-lock.json", "frontend/tsconfig.json"}
PUBLIC_IMAGES = {
    'docs/images/container-architecture.drawio.png': '517427dda169c8d2c6f4046f06b4e954d537ae42f80f59b890c1f38977fa4711',
    'docs/images/local-workbench.png': '15b2043ef8389de1de46edce38d9cba66d71abd046fd950cd181f8674dddec64',
}
VENDORED_ASSETS = {
    "src/workflow_doctor/api/assets/swagger-ui-bundle.js": "36eeb4d5640b9c036b1d0f854499af1cceebbdb260b790a03a18be5e8488fbf5",
    "src/workflow_doctor/api/assets/swagger-ui.css": "c3cfe8248c4b0b89673600fb829924eafbac6de4bc4b2b06f5f5243483074d0a",
    "src/workflow_doctor/api/assets/LICENSE.txt": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
    "src/workflow_doctor/api/assets/swagger-ui-bundle.js.LICENSE.txt": "37eb6e7e59aed57b2c1acf076574b818ea07b74265717e0bd67b59e0baf9abbb",
}
PUBLIC_TEXT_LOGS = set()
PUBLIC_DEPLOYMENT = {'.dockerignore', 'deploy/backend/Dockerfile', 'deploy/frontend/Dockerfile',
                     'deploy/backend/requirements.lock', 'deploy/backend/build.lock',
                     'deploy/backend/test.lock', 'deploy/frontend/nginx.conf',
                     'deploy/frontend/proxy.conf', 'deploy/frontend/static-headers.conf'}
PRIVATE_PARTS = {"private", "private-workflows", "real-workflows", "local-inputs", "uploads",
                 "secrets", "credentials", "logs", ".aws", ".ssh",
                 ".tmp", ".runtime", "optimization-test-results", "playwright-optimization-report", "native-test-results", "playwright-native-report", "tmp", "temp", "output", ".playwright-cli", "node_modules", "dist",
                 "coverage", "test-results", "playwright-report", "security-test-results",
                 "playwright-security-report", "docker-test-results", "playwright-docker-report"}
SECRET_PATTERNS = {
    "PRIVATE_KEY": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS_ACCESS_KEY": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "GITHUB_TOKEN": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "OPENAI_KEY": re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{24,}\b"),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b"),
}


def path_issue(path: str) -> str | None:
    if path in VENDORED_ASSETS:
        return None
    parts = PurePosixPath(path).parts
    lower = path.lower()
    if (not parts or path.startswith("/") or ".." in parts
            or any(part.startswith(".") and part not in (".github", ".gitignore", ".gitattributes", ".dockerignore", ".env.example") for part in parts)
            or any(part.lower() in PRIVATE_PARTS or part.lower().startswith((".venv", "venv")) for part in parts)
            or any(any(marker in part.lower() for marker in ("credential", "secret", "api_key", "api-key", "apikey", "token")) for part in parts)
            or any(part.lower().startswith(".env") and part != ".env.example" for part in parts)
            or ".local." in lower):
        return "PRIVATE_PATH"
    suffix = PurePosixPath(path).suffix.lower()
    if path in PUBLIC_IMAGES:
        return None
    if path in PUBLIC_DEPLOYMENT:
        return None
    if suffix == ".json" and path not in PUBLIC_JSON | PUBLIC_FRONTEND_CONFIG:
        return "UNREVIEWED_JSON"
    if suffix == ".html":
        return None if path in PUBLIC_HTML | {"frontend/index.html"} else "UNREVIEWED_HTML"
    if suffix == ".txt" and path not in PUBLIC_TEXT_LOGS:
        return "UNREVIEWED_TEXT_LOG"
    if suffix in (".py", ".md", ".toml", ".yml", ".yaml", ".json", ".txt"):
        return None
    if suffix in (".ts", ".vue", ".css") and (path.startswith(("frontend/src/", "frontend/tests/", "frontend/e2e/"))
            or path in ("frontend/vite.config.ts", "frontend/playwright.config.ts", "frontend/playwright.security.config.ts", "frontend/playwright.docker.config.ts", "frontend/playwright.native.config.ts", "frontend/playwright.optimization.config.ts")):
        return None
    if path in (".gitignore", ".gitattributes", ".env.example", "LICENSE"):
        return None
    if path in ('start.ps1', 'stop.ps1', 'status.ps1', 'scripts/native.ps1'):
        return None
    return "UNREVIEWED_FILE_TYPE"


def review_blob(path: str, raw: bytes, mode: str = "100644") -> list[dict]:
    issue = path_issue(path)
    if issue or mode not in ("100644", "100755"):
        return [{"file": path, "code": issue or "NON_REGULAR_GIT_ENTRY"}]
    if path in VENDORED_ASSETS:
        return [] if hashlib.sha256(raw).hexdigest() == VENDORED_ASSETS[path] else [{"file": path, "code": "VENDORED_ASSET_HASH"}]
    if path in PUBLIC_IMAGES:
        return [] if raw.startswith(b'\x89PNG\r\n\x1a\n') and hashlib.sha256(raw).hexdigest() == PUBLIC_IMAGES[path] else [{"file": path, "code": "PUBLIC_IMAGE_HASH"}]
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError:
        return [{"file": path, "code": "NON_UTF8_FILE"}]
    findings = []
    for index, line in enumerate(text.splitlines(), 1):
        for code, pattern in SECRET_PATTERNS.items():
            if pattern.search(line):
                findings.append({"file": path, "line": index, "code": code})
    return findings


def main() -> int:
    try:
        index = subprocess.run(["git", "ls-files", "--stage", "-z"], capture_output=True, check=True).stdout
        if not index:
            print(json.dumps({"reviewed_files": 0, "error": "EMPTY_INDEX"}))
            return 2
        findings, count = [], 0
        for entry in index.split(b"\0"):
            if not entry:
                continue
            metadata, encoded_path = entry.split(b"\t", 1)
            mode, oid, stage = metadata.decode("ascii").split()
            path = encoded_path.decode("utf-8")
            count += 1
            issue = path_issue(path)
            if issue or stage != "0" or mode not in ("100644", "100755"):
                findings.append({"file": path, "code": issue or "NON_REGULAR_GIT_ENTRY"})
                continue
            size = int(subprocess.run(["git", "cat-file", "-s", oid], capture_output=True, check=True).stdout)
            if size > 2 * 1024 * 1024:
                findings.append({"file": path, "code": "REVIEW_SIZE_LIMIT"})
                continue
            raw = subprocess.run(["git", "cat-file", "blob", oid], capture_output=True, check=True).stdout
            findings.extend(review_blob(path, raw, mode))
        print(json.dumps({"reviewed_files": count, "findings": findings,
                          "notice": "Local staged-file checks supplement human review; no data was uploaded."}, indent=2))
        return 1 if findings else 0
    except (OSError, ValueError, subprocess.CalledProcessError):
        print(json.dumps({"error": "Cannot safely review the local Git index"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
