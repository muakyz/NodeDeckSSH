"""Read a single SSH password using the local KeePassXC command-line tool."""
import os
from pathlib import Path
import shutil
import subprocess


def find_cli():
    for variable in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        directory = os.environ.get(variable)
        if directory:
            candidate = Path(directory) / "KeePassXC" / "keepassxc-cli.exe"
            if candidate.is_file():
                return str(candidate)
    return shutil.which("keepassxc-cli")


def read_password(cli, database, entry, master_password, key_file=""):
    if "\n" in master_password or "\r" in master_password:
        raise ValueError("KeePassXC ana parolası satır sonu içeremez.")
    args = [cli, "show", "--quiet", "--show-protected", "--attributes", "Password"]
    if key_file:
        args.extend(["--key-file", key_file])
        if not master_password:
            args.append("--no-password")
    args.extend(["--", database, entry])
    try:
        result = subprocess.run(
            args,
            input=(master_password + "\n").encode("utf-8"),
            capture_output=True,
            timeout=45,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("KeePassXC komut satırı aracı çalıştırılamadı veya zaman aşımına uğradı.") from None
    if result.returncode:
        raise RuntimeError("KeePassXC kaydı okunamadı. Kasa parolasını, anahtar dosyasını ve kayıt yolunu kontrol edin.")
    output = result.stdout
    if os.name == "nt":
        output = output.replace(b"\r\n", b"\n")
    try:
        password = output.removesuffix(b"\n").decode("utf-8")
    except UnicodeDecodeError:
        raise RuntimeError("KeePassXC çıktısı okunamadı.") from None
    if not password:
        raise RuntimeError("KeePassXC kaydında SSH parolası boş.")
    return password
