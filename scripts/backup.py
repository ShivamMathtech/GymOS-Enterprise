"""Write a custom-format PostgreSQL dump using Compose; never uses shell redirection."""

import argparse, subprocess, os
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("output")
p.add_argument("--compose", default="compose.yaml")
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
out = Path(a.output).resolve()
out.parent.mkdir(parents=True, exist_ok=True)
command = [
    "docker",
    "compose",
    "-f",
    a.compose,
    "exec",
    "-T",
    "db",
    "sh",
    "-c",
    'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-acl',
]
fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
try:
    with os.fdopen(fd, "wb") as f:
        subprocess.run(command, cwd=root, stdout=f, check=True)
except Exception:
    out.unlink(missing_ok=True)
    raise
print("Backup written to", out)
