"""Local folder definitions and display locations for vault entries."""
from pathlib import Path
import json
from tempfile import NamedTemporaryFile

from bridge_client import APP_DATA

FILE = APP_DATA / "folders.json"


def load():
    if not FILE.exists():
        return [], {}
    data = json.loads(FILE.read_text(encoding="utf-8"))
    paths, locations = data["folders"], data["locations"]
    if not isinstance(paths, list) or not isinstance(locations, dict):
        raise ValueError("Klasör dosyası geçersiz.")
    if any(not isinstance(path, str) for path in paths + list(locations.values())):
        raise ValueError("Klasör yolu geçersiz.")
    return paths, locations


def save(paths, locations):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(dir=FILE.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps({"folders": paths, "locations": locations}, ensure_ascii=False).encode("utf-8"))
        temporary.replace(FILE)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
