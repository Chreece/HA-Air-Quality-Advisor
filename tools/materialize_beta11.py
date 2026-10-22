"""Rebuild a checksum-pinned beta candidate from readable source diffs.

This staging-only job stores the checked candidate beneath candidate/. It does
not move feature/main/release refs, create a tag, or publish a release. Promotion
is a separate, explicit GitHub API operation after the candidate tree is read.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = "79a6c7a9fbeef887f6cf0df4f27cf8420d47c316"
BASE_TREE = "93e3e61c06e32b30476b60bccc6ac94e2b02be02"
ORIGINAL_TREE = "484f448d02348cef293357529b814eb23d44c48a"
FINAL_TREE = "79ea0aa8c0af26ce54f796f3759fedc83766a555"
BRANCH = "chore/materialize-beta11-20261022"
PATCH_HASH = "2afac8f34c3efac3ddfd340054242d611e9835fab7acab910248d019727c211a"
FIX_HASH = "5a461c83c7e4643ada6668b7f1af673eb58312d5fdc249c4629b15f0f14c52e3"


def git(*args: str, cwd: Path = ROOT, data: bytes | None = None, env=None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, input=data, env=env,
                          stdout=subprocess.PIPE, check=True).stdout.decode().strip()


def checked(data: bytes, digest: str) -> bytes:
    if hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError("Readable source diff checksum mismatch")
    return data


def main() -> None:
    if os.environ.get("GITHUB_REF_NAME") != BRANCH:
        raise RuntimeError("This helper is limited to its exact staging branch")
    if (ROOT / "candidate").exists():
        print("Verified candidate already stored; no further action")
        return
    head = git("rev-parse", "HEAD")
    if head != os.environ.get("GITHUB_SHA") or git("rev-parse", "HEAD^") != BASE:
        raise RuntimeError("Unexpected staging parent or HEAD")
    if git("rev-parse", f"{BASE}^{{tree}}") != BASE_TREE:
        raise RuntimeError("Unexpected source baseline tree")
    if git("status", "--porcelain"):
        raise RuntimeError("Staging checkout is not clean")
    parts = ROOT / ".github/beta11-source"
    if {p.name for p in parts.iterdir()} != {f"{i:02}.patch" for i in range(19)} | {"prepublish-fix.patch"}:
        raise RuntimeError("Unexpected readable patch file list")
    patch = checked(b"".join((parts / f"{i:02}.patch").read_bytes() for i in range(19)), PATCH_HASH)
    if len(patch) != 259242:
        raise RuntimeError("Incomplete source diff")
    fix = checked((parts / "prepublish-fix.patch").read_bytes(), FIX_HASH)
    with tempfile.TemporaryDirectory(prefix="hem-beta11-", dir=os.environ.get("RUNNER_TEMP")) as temp:
        work = Path(temp) / "source"
        git("worktree", "add", "--detach", str(work), BASE)
        try:
            git("apply", "--check", "--index", "-", cwd=work, data=patch)
            git("apply", "--index", "-", cwd=work, data=patch)
            subprocess.run([sys.executable, "generate_translations.py"], cwd=work, check=True)
            git("add", "-A", cwd=work)
            if git("write-tree", cwd=work) != ORIGINAL_TREE:
                raise RuntimeError("Regenerated candidate differs from tested source")
            git("apply", "--check", "--index", "-", cwd=work, data=fix)
            git("apply", "--index", "-", cwd=work, data=fix)
            if git("write-tree", cwd=work) != FINAL_TREE:
                raise RuntimeError("Prepublication fixes differ from tested source")
            subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=work, check=True)
            subprocess.run(["node", "--check", "custom_components/air_quality_advisor/frontend/air-quality-advisor-card.js"], cwd=work, check=True)
            subprocess.run(["node", "tests/card_test.cjs"], cwd=work, check=True)
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(temp) / "storage-index"))
            git("read-tree", head, env=env)
            git("read-tree", "--prefix=candidate/", FINAL_TREE, env=env)
            storage_tree = git("write-tree", env=env)
            commit = git("commit-tree", storage_tree, "-p", head,
                         data=b"chore: store verified beta11 source tree for explicit promotion\n")
            print(f"VERIFIED_CANDIDATE_TREE={FINAL_TREE}")
            print(f"STORAGE_COMMIT={commit}")
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
                out.write(f"commit={commit}\ntree={FINAL_TREE}\n")
        finally:
            git("worktree", "remove", "--force", str(work))


if __name__ == "__main__":
    main()
