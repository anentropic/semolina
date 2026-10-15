"""
Does C's credential-free subprocess keep credentials away from the user's module? Throwaway.

Run from the repository root (Linux):

    uv run python .planning/research/d9-prototypes/c_isolation.py

Builds a project directory holding every credential source Semolina reads, plus the ones
warehouse drivers read from the home directory, then plays the CLI: a parent process with
secrets in its environment and an open socket (standing in for a warehouse connection)
runs ``reader_c`` on a "committed model" whose module-level code goes looking for them.
That module runs in the child, with ``reader_c``'s allowlisted environment.

It runs twice: as the current user (root in the sandbox this was measured in), and with
both processes dropped to ``nobody`` via ``setpriv``, which is the ordinary case of a CLI
and its child running as the same unprivileged user.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

SPY = '''
import json, os, pathlib
here = pathlib.Path(__file__).resolve().parent
found = {}
found["env_vars_with_secret"] = sorted(k for k, v in os.environ.items() if "SECRET" in v)
found["home_seen_by_child"] = os.path.expanduser("~")

def read(p):
    try:
        return "SECRET" in pathlib.Path(p).read_text()
    except OSError as e:
        return f"refused: {type(e).__name__}"

found[".semolina.toml via cwd"] = read(".semolina.toml")
found[".semolina.toml via __file__"] = read(here / ".semolina.toml")
found[".env via __file__"] = read(here / ".env")
try:
    os.chdir(here)
    from semolina.config import warehouse_config
    cfg = warehouse_config("snowflake")
    pw = getattr(cfg, "password", None)
    pw = pw.get_secret_value() if hasattr(pw, "get_secret_value") else pw
    found["semolina warehouse_config() password"] = pw
except Exception as e:
    found["semolina warehouse_config() password"] = f"error: {type(e).__name__}: {e}"
try:
    parent_env = pathlib.Path(f"/proc/{os.getppid()}/environ").read_bytes().split(b"\\0")
    pairs = dict(x.decode().split("=", 1) for x in parent_env if b"=" in x)
    found["parent /proc/PPID/environ secrets"] = sorted(k for k, v in pairs.items() if "SECRET" in v)
    home = pairs.get("HOME")
    found["parent HOME (from /proc)"] = home
    found["~/.snowflake/connections.toml via parent HOME"] = read(f"{home}/.snowflake/connections.toml")
except OSError as e:
    found["parent /proc/PPID/environ secrets"] = f"refused: {type(e).__name__}"
fds = {}
for f in os.listdir("/proc/self/fd"):
    try:
        fds[int(f)] = os.readlink(f"/proc/self/fd/{f}")
    except OSError:
        pass
found["open fds"] = {k: fds[k] for k in sorted(fds)}
(here / "spy.json").write_text(json.dumps(found, indent=1))
'''


def parent(project: Path) -> None:
    """The CLI's side: secrets in the environment, a socket open, then reader_c."""
    sys.path.insert(0, str(HERE))
    import reader_c

    a, b = socket.socketpair()  # a stand-in for an open warehouse connection
    os.chdir(project)
    try:
        reader_c.run_child("models", project / "models.py")
    except (ValueError, ModuleNotFoundError) as e:
        # The system python has no semolina; the spy has already run by then.
        print(f"child failed after import: {e}", file=sys.stderr)
    finally:
        a.close()
        b.close()
    print((project / "spy.json").read_text())


def build(root: Path) -> tuple[Path, Path]:
    project, home = root / "project", root / "home"
    (home / ".snowflake").mkdir(parents=True)
    project.mkdir()
    (project / ".semolina.toml").write_text(
        '[connections.snowflake]\naccount = "acme"\nuser = "u"\npassword = "TOML-SECRET"\n'
    )
    (project / ".env").write_text("SNOWFLAKE_PASSWORD=DOTENV-SECRET\n")
    (home / ".snowflake/connections.toml").write_text('[default]\npassword = "HOME-SECRET"\n')
    (project / "models.py").write_text(SPY)
    for p in [root, *root.rglob("*")]:
        p.chmod(0o777 if p.is_dir() else 0o666)
    return project, home


def main() -> None:
    if sys.argv[1:2] == ["--parent"]:
        parent(Path(sys.argv[2]))
        return
    results = {}
    nobody = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "--"]
    # The venv's interpreter lives under /root, which nobody cannot reach: use the system one.
    for label, prefix, python in (
        ("current user", [], sys.executable),
        ("nobody (parent and child)", nobody, "/usr/bin/python3"),
    ):
        root = Path(tempfile.mkdtemp(prefix="d9c-"))
        root.chmod(0o777)
        try:
            project, home = build(root)
            env = {
                "PATH": os.environ["PATH"],
                "HOME": str(home),
                "SNOWFLAKE_PASSWORD": "ENV-SECRET",
                "DATABRICKS_TOKEN": "ENV-SECRET-TOKEN",
            }
            out = subprocess.run(
                [*prefix, python, __file__, "--parent", str(project)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            results[label] = json.loads(out.stdout) if out.returncode == 0 else out.stderr[-2000:]
        finally:
            shutil.rmtree(root, ignore_errors=True)
    text = json.dumps(results, indent=1)
    (HERE / "c_isolation_results.json").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
