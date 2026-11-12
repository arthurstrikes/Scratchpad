"""Keep our own saved reports somewhere that survives a machine reset.

The report's memory - the track record, the "awaiting listing" section, "change since
last report", recently listed - is read from the dataset and listing files in the output
folder. That folder lives on a cloud machine that can be replaced (it was on 28 Oct 2026,
and every report from 15-27 Oct was lost). So after a real run the figures are copied to
the repository's `history` branch, and before a run any file missing locally is restored
from it.

Only IPO figures and report text are stored (datasets, listing results, report .txt).
Never images, never raw page snapshots, never anything from the environment.
Best-effort by design: a failure is logged and never changes the run.
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import tempfile
from typing import Callable, Optional

BRANCH = "history"
PATTERNS = ("ipo-watch-*-dataset.json", "ipo-watch-*.txt", "ipo-watch-listing-*.json")
TIMEOUT_S = 90


def _git(args: list[str], cwd: str, timeout: int = TIMEOUT_S) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)


def _repo_root(start: str) -> Optional[str]:
    try:
        r = _git(["rev-parse", "--show-toplevel"], start, 20)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def _wanted(folder: str) -> list[str]:
    out: list[str] = []
    for pat in PATTERNS:
        out += glob.glob(os.path.join(folder, pat))
    return sorted(set(out))


def restore(outdir: str, log: Callable[[str], None] = lambda m: None,
            repo_dir: Optional[str] = None) -> int:
    """Copy into `outdir` every saved file the history branch has and the folder lacks.
    Never overwrites a local file. Returns how many were restored."""
    try:
        root = _repo_root(repo_dir or os.path.dirname(os.path.abspath(__file__)))
        if not root:
            log("history -> restore skipped (not inside a git checkout)")
            return 0
        f = _git(["fetch", "--depth=1", "origin", BRANCH], root)
        if f.returncode != 0:
            log("history -> restore skipped (no history branch reachable)")
            return 0
        os.makedirs(outdir, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            a = subprocess.run(f"git archive FETCH_HEAD | tar -x -C {tmp}", shell=True, cwd=root,
                               capture_output=True, text=True, timeout=TIMEOUT_S)
            if a.returncode != 0:
                log("history -> restore skipped (could not read the history branch)")
                return 0
            n = 0
            for path in _wanted(tmp):
                dest = os.path.join(outdir, os.path.basename(path))
                if not os.path.exists(dest):
                    shutil.copy2(path, dest)
                    n += 1
        log(f"history -> restored {n} saved file(s) the folder was missing" if n
            else "history -> nothing missing locally")
        return n
    except Exception as exc:  # noqa: BLE001
        log(f"history -> restore skipped ({type(exc).__name__}: {exc})")
        return 0


def save(outdir: str, log: Callable[[str], None] = lambda m: None,
         repo_dir: Optional[str] = None) -> bool:
    """Copy the datasets, listing results and report text to the history branch and push.
    True if something new was pushed."""
    try:
        files = _wanted(outdir)
        if not files:
            log("history -> nothing to save")
            return False
        root = _repo_root(repo_dir or os.path.dirname(os.path.abspath(__file__)))
        if not root:
            log("history -> save skipped (not inside a git checkout)")
            return False
        origin = _git(["remote", "get-url", "origin"], root, 20).stdout.strip()
        with tempfile.TemporaryDirectory() as tmp:
            dest = os.path.join(tmp, "h")
            c = _git(["clone", "--quiet", "--depth", "1", "--branch", BRANCH, origin, dest], tmp)
            if c.returncode != 0:
                log("history -> save skipped (the history branch could not be fetched)")
                return False
            for path in files:
                shutil.copy2(path, os.path.join(dest, os.path.basename(path)))
            _git(["add", "-A"], dest, 30)
            if _git(["diff", "--cached", "--quiet"], dest, 30).returncode == 0:
                log("history -> already up to date")
                return False
            who = ["-c", "user.name=ipo-watch[bot]", "-c", "user.email=ipo-watch@users.noreply.github.com"]
            m = _git([*who, "commit", "--quiet", "-m", "History: saved reports"], dest, 30)
            if m.returncode != 0:
                log("history -> save skipped (commit failed)")
                return False
            p = _git(["push", "--quiet", "origin", BRANCH], dest)
            if p.returncode != 0:
                log("history -> save FAILED (push refused: " + (p.stderr.strip().splitlines() or ["?"])[-1][:120] + ")")
                return False
        log("history -> saved to the history branch")
        return True
    except Exception as exc:  # noqa: BLE001
        log(f"history -> save skipped ({type(exc).__name__}: {exc})")
        return False
