"""Persist connection metadata for manual and KeePassXC profiles."""
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from bridge_client import APP_DATA

PROFILES_FILE = APP_DATA / "profiles.json"
PROFILE_FIELDS = ("id", "name", "host", "port", "username", "group", "source",
                  "database", "xc_entry", "key_file")


OPTIONAL_FIELDS = ("protected_password", "auth", "ssh_key")


def load_profiles():
    if not PROFILES_FILE.exists():
        return []
    records = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
    return validate_profiles(records)


def validate_profiles(records):
    if not isinstance(records, list):
        raise ValueError("Profil dosyası geçersiz.")
    for record in records:
        if (not isinstance(record, dict)
                or record.get("source") not in ("manual", "xc")
                or any(not isinstance(record.get(field), str) for field in PROFILE_FIELDS)
                or any(not isinstance(record.get(field, ""), str) for field in OPTIONAL_FIELDS)
                or not record["id"].startswith("local:")
                or not record["port"].isdigit()
                or not 1 <= int(record["port"]) <= 65535):
            raise ValueError("Profil dosyasında geçersiz kayıt var.")
    return [{field: record.get(field, "") for field in PROFILE_FIELDS + OPTIONAL_FIELDS}
            for record in records]


def save_profiles(records):
    PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = [{field: record.get(field, "") for field in PROFILE_FIELDS + OPTIONAL_FIELDS} for record in records]
    temporary = None
    try:
        with NamedTemporaryFile(dir=PROFILES_FILE.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
        temporary.replace(PROFILES_FILE)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
