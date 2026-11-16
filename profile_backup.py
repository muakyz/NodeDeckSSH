"""Export and restore the local workspace without decrypting saved passwords."""
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile

from bridge_client import APP_DATA
from local_profiles import validate_profiles
from password_vault import PREFIX

FILES = ("profiles.json", "password-vault.json", "folders.json")
MAX_FILE_SIZE = 16 * 1024 * 1024


def export_backup(destination):
    destination = Path(destination)
    if destination.resolve() in {(APP_DATA / name).resolve() for name in FILES}:
        raise ValueError("Choose a ZIP destination outside the internal data files.")
    with NamedTemporaryFile(dir=Path(destination).parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with ZipFile(temporary, "w", ZIP_DEFLATED) as archive:
            for name in FILES:
                path = APP_DATA / name
                if path.is_file():
                    archive.write(path, name)
            if "profiles.json" not in archive.namelist():
                archive.writestr("profiles.json", "[]")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def read_backup(source):
    with ZipFile(source) as archive:
        members = archive.infolist()
        names = [entry.filename for entry in members]
        if ("profiles.json" not in names or len(names) != len(set(names))
                or any(item.filename not in FILES or item.file_size > MAX_FILE_SIZE for item in members)):
            raise ValueError("Invalid NodeDeck backup.")
        files = {name: archive.read(name) for name in names}
    profiles = validate_profiles(json.loads(files["profiles.json"]))
    passwords = [profile["protected_password"] for profile in profiles if profile["protected_password"]]
    if any(not value.startswith(PREFIX) for value in passwords):
        raise ValueError("Open the original local vault to migrate legacy passwords before exporting.")
    if passwords and "password-vault.json" not in files:
        raise ValueError("The backup is missing its password vault header.")
    if "password-vault.json" in files:
        from password_vault import decode
        header = json.loads(files["password-vault.json"])
        if header["version"] != 1 or len(decode(header["salt"])) != 16 or len(decode(header["check"])) < 40:
            raise ValueError("Invalid password vault header.")
    if "folders.json" in files:
        data = json.loads(files["folders.json"])
        if (not isinstance(data["folders"], list) or not isinstance(data["locations"], dict)
                or any(not isinstance(value, str) for value in data["folders"] + list(data["locations"].values()))):
            raise ValueError("Invalid folder data.")
    return files


def restore_backup(files):
    APP_DATA.mkdir(parents=True, exist_ok=True)
    previous = {name: (APP_DATA / name).read_bytes() for name in FILES if (APP_DATA / name).exists()}

    def replace(name, content):
        path = APP_DATA / name
        if content is None:
            path.unlink(missing_ok=True)
            return
        with NamedTemporaryFile(dir=APP_DATA, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        try:
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    changed = []
    try:
        for name in FILES:
            replace(name, files.get(name))
            changed.append(name)
    except OSError:
        for name in reversed(changed):
            replace(name, previous.get(name))
        raise
