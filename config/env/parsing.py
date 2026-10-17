import os


def env_bool(key: str, *, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def env_csv(key: str, *, default: tuple[str, ...] = ()) -> list[str]:
    raw = (os.environ.get(key) or "").strip()
    if not raw:
        return list(default)
    return [part.strip() for part in raw.split(",") if part.strip()]
