"""Integrate a lead's finished story into main.

Run from inside a lead worktree, on its lead branch, with a clean tree:

    python scripts/integrate.py 2-1-survey-upload-endpoint [--status review]

Steps, all under a repo-wide lock so only one lead integrates at a time:
merge main -> run the gate -> record the story status -> fast-forward main.

Exit codes: 0 ok, 1 usage/state error, 2 lock timeout, 3 merge conflict,
4 gate failed, 5 fast-forward of main failed.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

STATUS_FILE = Path("planning/implementation-artifacts/sprint-status.yaml")
LOCK_STALE_S = 30 * 60
LOCK_WAIT_S = 20 * 60
GATE_TIMEOUT_S = 25 * 60
STORY_KEY = re.compile(r"^\d+-\d+-[a-z0-9-]+$")


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8"
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{proc.stdout}{proc.stderr}")
    return proc.stdout.strip()


def fail(code: int, msg: str) -> None:
    print(f"INTEGRATE_FAILED({code}): {msg}", file=sys.stderr)
    sys.exit(code)


def main_worktree() -> Path:
    """Return the worktree that has `main` checked out."""
    current: Path | None = None
    for line in git("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            current = Path(line.removeprefix("worktree "))
        elif line == "branch refs/heads/main" and current is not None:
            return current
    fail(1, "no worktree has main checked out")
    raise AssertionError


class Lock:
    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self) -> Lock:
        deadline = time.monotonic() + LOCK_WAIT_S
        while True:
            try:
                self.path.mkdir()
                (self.path / "owner").write_text(
                    f"{Path.cwd()}\n{datetime.now(UTC).isoformat()}\n", encoding="utf-8"
                )
                return self
            except FileExistsError:
                age = time.time() - self.path.stat().st_mtime
                if age > LOCK_STALE_S:
                    print(f"breaking stale lock ({int(age)}s old)")
                    shutil.rmtree(self.path, ignore_errors=True)
                    continue
                if time.monotonic() > deadline:
                    fail(2, f"lock held too long: {self.path}")
                time.sleep(15)

    def __exit__(self, *exc: object) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


def run_gate(root: Path) -> None:
    cmds: list[list[str]] = []
    if (root / "pyproject.toml").exists():
        cmds.append(["uv", "run", "poe", "gate"])
    if (root / "web" / "package.json").exists():
        pnpm = shutil.which("pnpm")
        if pnpm is None:
            fail(4, "web/ exists but pnpm is not on PATH")
        cmds.append([pnpm, "-C", "web", "run", "gate"])
    for cmd in cmds:
        print("gate:", " ".join(cmd), flush=True)
        try:
            proc = subprocess.run(
                cmd, cwd=root, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=GATE_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            fail(4, f"gate timed out after {GATE_TIMEOUT_S}s: {' '.join(cmd)}")
        if proc.returncode != 0:
            tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-80:])
            print(tail)
            fail(4, f"gate failed: {' '.join(cmd)}")


def set_status(root: Path, key: str, status: str) -> None:
    path = root / STATUS_FILE
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    story = re.compile(rf"^(\s+{re.escape(key)}:\s*)(\S+)(.*)$")
    hits = [i for i, line in enumerate(lines) if story.match(line.rstrip("\r\n"))]
    if len(hits) != 1:
        fail(1, f"story key {key!r} found {len(hits)} times in {STATUS_FILE}")
    i = hits[0]
    m = story.match(lines[i].rstrip("\r\n"))
    assert m is not None
    eol = lines[i][len(lines[i].rstrip("\r\n")):]
    lines[i] = f"{m.group(1)}{status}{m.group(3)}{eol}"

    # Epic status follows its stories: done when every story is done.
    epic = key.split("-", 1)[0]
    entry = re.compile(rf"^\s+({epic}-\d+-[a-z0-9-]+):\s*(\S+)")
    statuses = [m.group(2) for line in lines if (m := entry.match(line))]
    epic_status = "done" if all(s == "done" for s in statuses) else "in-progress"
    epic_line = re.compile(rf"^(\s+epic-{epic}:\s*)(\S+)(.*)$")
    today = datetime.now(UTC).date().isoformat()
    for j, line in enumerate(lines):
        body = line.rstrip("\r\n")
        tail = line[len(body):]
        if m := epic_line.match(body):
            lines[j] = f"{m.group(1)}{epic_status}{m.group(3)}{tail}"
        elif body.startswith("last_updated:"):
            lines[j] = f"last_updated: {today}{tail}"
    path.write_text("".join(lines), encoding="utf-8", newline="")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("story_key")
    ap.add_argument("--status", choices=["done", "review"], default="done")
    args = ap.parse_args()
    if not STORY_KEY.match(args.story_key):
        fail(1, f"bad story key {args.story_key!r}")

    root = Path(git("rev-parse", "--show-toplevel"))
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch == "main" or not branch.startswith("lead-"):
        fail(1, f"run from a lead worktree, not branch {branch!r}")
    if git("status", "--porcelain"):
        fail(1, "working tree not clean; commit first")

    common = Path(git("rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = root / common
    main_wt = main_worktree()

    with Lock(common / "reefcase-integrate.lock"):
        proc = subprocess.run(
            ["git", "merge", "main", "--no-edit"], cwd=root, capture_output=True, text=True
        )
        if proc.returncode != 0:
            conflicts = git("diff", "--name-only", "--diff-filter=U", cwd=root, check=False)
            git("merge", "--abort", cwd=root, check=False)
            fail(3, f"merge conflict with main in:\n{conflicts}")

        run_gate(root)

        set_status(root, args.story_key, args.status)
        git("add", str(STATUS_FILE), cwd=root)
        if git("diff", "--cached", "--name-only", cwd=root):  # empty on a retry
            git("commit", "-m", f"status: {args.story_key} -> {args.status}", cwd=root)

        if git("status", "--porcelain", cwd=main_wt):
            fail(5, f"main worktree {main_wt} has uncommitted changes; leave it clean")
        proc = subprocess.run(
            ["git", "merge", "--ff-only", branch], cwd=main_wt, capture_output=True, text=True
        )
        if proc.returncode != 0:
            fail(5, f"fast-forward failed:\n{proc.stdout}{proc.stderr}")

    print(f"INTEGRATED {args.story_key} -> {args.status} (main at {git('rev-parse', '--short', 'main')})")


if __name__ == "__main__":
    main()
