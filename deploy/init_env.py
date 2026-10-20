"""Create .env.production from the example, with fresh random secrets.  Never overwrites an existing file.
Run from the repo root:  backend/.venv/bin/python deploy/init_env.py"""
import re
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / ".env.production"
if target.exists():
    raise SystemExit(".env.production already exists; leaving it alone")

text = (ROOT / ".env.production.example").read_text()
local = {}
env = ROOT / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            local[k.strip()] = v.strip()


def fill(key: str, value: str) -> None:
    global text
    text = re.sub(rf"^{key}=.*$", f"{key}={value}", text, flags=re.M)


fill("SECRET_KEY", secrets.token_urlsafe(48))
fill("STUDENT_CODE", "bruin-" + secrets.token_hex(3))
fill("PROFESSOR_CODE", "prof-" + secrets.token_hex(4))
if local.get("OPENROUTER_API_KEY"):
    fill("OPENROUTER_API_KEY", local["OPENROUTER_API_KEY"])  # reuse your local key; stays on this machine
target.write_text(text)
target.chmod(0o600)
print(f"wrote {target} (permissions 600). Fill in DATABASE_URL and ALLOWED_ORIGINS; see the codes inside the file.")
