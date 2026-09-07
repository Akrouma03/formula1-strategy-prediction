"""Fail CI if private artifacts or recognisable secret formats enter the repo.

This is a guardrail, not a comprehensive secret scanner. Never print matches.
"""

from __future__ import annotations

import re
import subprocess

from f1strategy.paths import ROOT

PRIVATE_SUFFIXES = {".doc", ".docx", ".pdf", ".pem", ".key", ".joblib", ".pkl"}
SECRET_PATTERNS = [
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    rb"gh[pousr]_[A-Za-z0-9]{36,}",
    rb"github_pat_[A-Za-z0-9_]{60,}",
    rb"AKIA[0-9A-Z]{16}",
    rb"sk-(?:proj-)?[A-Za-z0-9_-]{32,}",
]


def problems(name: str, content: bytes) -> list[str]:
    from pathlib import PurePosixPath

    path = PurePosixPath(name)
    result = []
    if path.suffix.lower() in PRIVATE_SUFFIXES or path.name == ".env" or path.name.startswith(".env."):
        result.append("private artifact")
    if path.suffix.lower() not in {".png", ".jpg", ".webp", ".ico"}:
        if any(re.search(pattern, content) for pattern in SECRET_PATTERNS):
            result.append("possible secret")
    return result


def main() -> int:
    files = (
        subprocess.check_output(
            [
                "git",
                "-c",
                f"safe.directory={ROOT.as_posix()}",
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            cwd=ROOT,
        )
        .decode("utf-8")
        .split("\0")
    )
    failures = []
    for name in sorted(set(filter(None, files))):
        path = ROOT / name
        if path.is_file():
            failures.extend(f"{name}: {reason}" for reason in problems(name, path.read_bytes()))
    if failures:
        print("\n".join(failures))
        return 1
    print("Public-file guard passed: no forbidden tracked artifacts or recognised secret formats.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
