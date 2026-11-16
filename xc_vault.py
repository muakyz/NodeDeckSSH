"""Read SSH connection profiles from a KeePassXC-compatible KDBX file."""
from preferences import tr
from urllib.parse import urlsplit
from pathlib import Path
from tempfile import NamedTemporaryFile

from pykeepass import PyKeePass
from pykeepass.exceptions import CredentialsError


def load_ssh_hub(filename, password, keyfile):
    try:
        database = PyKeePass(filename, password=password or None, keyfile=keyfile or None)
    except CredentialsError:
        raise ValueError(tr("Kasa açılamadı. Ana parolayı ve varsa anahtar dosyasını kontrol edin.")) from None
    except Exception:
        raise ValueError(tr("KDBX dosyası okunamadı. Dosya yolunu ve kasa biçimini kontrol edin.")) from None

    hubs = [group for group in database.root_group.subgroups if group.name == "SSH Hub"]
    if not hubs:
        return [], {}, 0
    profiles = []
    passwords = {}
    skipped = 0
    pending = [(group, "SSH Hub") for group in hubs]
    while pending:
        group, path = pending.pop()
        pending.extend((child, f"{path}/{child.name}") for child in group.subgroups)
        for entry in group.entries:
            try:
                target = urlsplit((entry.url or "").strip())
                port = target.port if target.port is not None else 22
                if (target.scheme != "ssh" or not target.hostname or not port
                        or any(char.isspace() for char in target.hostname)
                        or target.password is not None or not entry.username):
                    raise ValueError()
            except ValueError:
                skipped += 1
                continue
            identifier = f"hub:{entry.uuid}"
            profiles.append({
                "id": identifier, "name": entry.title or target.hostname,
                "host": target.hostname, "port": str(port), "username": entry.username,
                "group": path, "source": "hub",
            })
            passwords[identifier] = entry.password or ""
    return profiles, passwords, skipped


def save_ssh_hub_entry(credentials, entry):
    filename, password, keyfile = credentials
    source = Path(filename)
    original = source.read_bytes()
    database = PyKeePass(filename, password=password or None, keyfile=keyfile or None)
    parent = database.root_group
    group = entry["group"].strip("/")
    segments = group.split("/") if group else []
    if not segments or segments[0] != "SSH Hub":
        segments.insert(0, "SSH Hub")
    for segment in segments:
        if segment:
            child = next((item for item in parent.subgroups if item.name == segment), None)
            parent = child if child is not None else database.add_group(parent, segment)
    host = entry["host"].strip("[]")
    if ":" in host:
        host = "[" + host + "]"
    database.add_entry(parent, entry["name"], entry["username"], entry["password"],
                       url=f'ssh://{host}:{entry["port"]}')
    with NamedTemporaryFile(dir=source.parent, suffix=".kdbx", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        database.save(str(temporary))
        if source.read_bytes() != original:
            raise RuntimeError("The KeePassXC file changed. Refresh and try again.")
        temporary.replace(source)
    finally:
        temporary.unlink(missing_ok=True)
