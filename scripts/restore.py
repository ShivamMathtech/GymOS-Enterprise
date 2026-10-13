"""Restore ONLY into a new *_restore database. Existing databases are never dropped."""

import argparse, re, subprocess
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("dump")
p.add_argument("--database", required=True)
p.add_argument("--compose", default="compose.yaml")
a = p.parse_args()
if not re.fullmatch(r"[a-z][a-z0-9_]{0,45}_restore", a.database):
    raise SystemExit("Use a new safe database name ending in _restore")
root = Path(__file__).resolve().parents[1]
dump = Path(a.dump).resolve()
if not dump.is_file():
    raise SystemExit("Dump file not found")
base = ["docker", "compose", "-f", a.compose, "exec", "-T", "db"]
# Name is validated and passed as a positional argument, never interpolated into shell source.
subprocess.run(
    base
    + [
        "sh",
        "-c",
        'test "$1" != "$POSTGRES_DB" && exec createdb -U "$POSTGRES_USER" "$1"',
        "restore",
        a.database,
    ],
    cwd=root,
    check=True,
)
with dump.open("rb") as f:
    subprocess.run(
        base
        + [
            "sh",
            "-c",
            'exec pg_restore -U "$POSTGRES_USER" -d "$1" --no-owner --no-acl --exit-on-error',
            "restore",
            a.database,
        ],
        cwd=root,
        stdin=f,
        check=True,
    )
print(
    "Restored into", a.database, "; review before switching any application connection."
)
