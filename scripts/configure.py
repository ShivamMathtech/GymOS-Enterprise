"""Create local development secrets once. Run with Python 3.12+. Never overwrites existing files."""

from pathlib import Path
import secrets, os

root = Path(__file__).resolve().parents[1]


def private_write(path, text):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    rootenv = root / ".env"
    backend = root / "backend/.env"
    if rootenv.exists() and backend.exists():
        print("Existing configuration preserved.")
        return
    if rootenv.exists() or backend.exists():
        raise SystemExit(
            "Partial configuration exists. Complete the other .env using its example; no files were changed."
        )
    password = secrets.token_urlsafe(32)
    key = secrets.token_hex(48)
    private_write(
        rootenv,
        f"POSTGRES_USER=gymos\nPOSTGRES_PASSWORD={password}\nPOSTGRES_DB=gymos\nPOSTGRES_PORT=5432\n".replace(
            "\\n", "\n"
        ),
    )
    content = (
        (root / "backend/.env.example")
        .read_text()
        .replace("CHANGE_DATABASE_PASSWORD", password)
        .replace("CHANGE_RUN_SCRIPTS_CONFIGURE_PY_TO_GENERATE", key)
    )
    private_write(backend, content)
    if not (root / "frontend/.env").exists():
        private_write(
            root / "frontend/.env", (root / "frontend/.env.example").read_text()
        )
    print("Local configuration created. Keep .env files private.")


if __name__ == "__main__":
    main()
