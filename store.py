"""Persist a submission (JSON + CV) to a private GitHub repo via a write deploy key."""

from __future__ import annotations

import base64
import os
import subprocess
import shutil
import tempfile
import time
from pathlib import Path

class StorageError(Exception):
    pass


def _run(cmd: list[str], cwd: str | None = None, env: dict | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _ssh_env(key_path: Path) -> dict:
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = (
        f"ssh -i {key_path} -o IdentitiesOnly=yes "
        "-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/tmp/hiring-known-hosts"
    )
    # Prevent leaking the user's ambient git/gh credentials.
    env.pop("GIT_ASKPASS", None)
    env.pop("GH_TOKEN", None)
    env.pop("GITHUB_TOKEN", None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def save_submission(folder_name: str, json_text: str, cv_bytes: bytes, cv_filename: str) -> str:
    repo = os.environ.get("SUBMISSIONS_REPO", "").strip()
    branch = os.environ.get("SUBMISSIONS_BRANCH", "main").strip() or "main"
    key_b64 = os.environ.get("DEPLOY_KEY_B64", "").strip()
    if not repo or "/" not in repo:
        raise StorageError("SUBMISSIONS_REPO is not configured")
    if not key_b64:
        raise StorageError("DEPLOY_KEY_B64 is not configured")

    try:
        key = base64.b64decode(key_b64)
    except Exception as exc:
        raise StorageError("DEPLOY_KEY_B64 is invalid") from exc

    safe_cv = Path(cv_filename).name
    if not safe_cv:
        safe_cv = "cv.bin"

    last_err = "unknown error"
    with tempfile.TemporaryDirectory(prefix="hiring-sub-") as tmp:
        tmp_path = Path(tmp)
        key_path = tmp_path / "id_ed25519"
        key_path.write_bytes(key if key.endswith(b"\n") else key + b"\n")
        key_path.chmod(0o600)
        env = _ssh_env(key_path)
        work = tmp_path / "repo"
        remotes = [
            f"ssh://git@ssh.github.com:443/{repo}.git",
            f"git@github.com:{repo}.git",
        ]

        for attempt in range(1, 6):
            if work.exists():
                shutil.rmtree(work, ignore_errors=True)
            remote = remotes[(attempt - 1) % len(remotes)]
            try:
                r = _run(
                    ["git", "clone", "--depth", "8", "--branch", branch, remote, str(work)],
                    env=env,
                    timeout=90,
                )
                if r.returncode != 0:
                    last_err = (r.stderr or r.stdout or "clone failed").strip()
                    time.sleep(attempt)
                    continue

                dest = work / "submissions" / folder_name
                dest.mkdir(parents=True, exist_ok=False)
                (dest / "application.json").write_text(json_text, encoding="utf-8")
                (dest / safe_cv).write_bytes(cv_bytes)

                _run(["git", "config", "user.email", "developer-application[bot]@users.noreply.github.com"], cwd=str(work), env=env)
                _run(["git", "config", "user.name", "Developer Application Form"], cwd=str(work), env=env)
                _run(["git", "add", "--", f"submissions/{folder_name}"], cwd=str(work), env=env)
                c = _run(
                    ["git", "commit", "-m", f"Add application {folder_name}"],
                    cwd=str(work),
                    env=env,
                )
                if c.returncode != 0:
                    last_err = (c.stderr or c.stdout or "commit failed").strip()
                    time.sleep(attempt)
                    continue
                # Rebase in case another submission landed.
                _run(["git", "pull", "--rebase", "origin", branch], cwd=str(work), env=env, timeout=60)
                p = _run(["git", "push", "origin", branch], cwd=str(work), env=env, timeout=90)
                if p.returncode != 0:
                    last_err = (p.stderr or p.stdout or "push failed").strip()
                    time.sleep(attempt)
                    continue
                return f"{repo}/submissions/{folder_name}"
            except subprocess.TimeoutExpired:
                last_err = "git operation timed out"
                time.sleep(attempt)
            except FileExistsError:
                # extremely unlikely collision; caller should use unique folder names
                last_err = "submission folder already exists"
                time.sleep(attempt)
            except Exception as exc:
                last_err = str(exc)
                time.sleep(attempt)

    raise StorageError(f"could not store submission: {last_err[:300]}")
