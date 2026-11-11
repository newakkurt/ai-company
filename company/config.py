"""Small dependency-free local .env loader."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]


def load_local_env(path: Path | str | None = None) -> int:
    """Load KEY=VALUE lines from .env without overriding existing process variables."""
    env_path = Path(path) if path is not None else ROOT / ".env"
    if not env_path.is_file():
        return 0
    loaded = 0
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key or not key.replace("_", "").isalnum():
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded
