"""Local-only KeePass 2 plugin client. No KDBX key or SSH password is stored here."""
from __future__ import annotations

import json
import os
from pathlib import Path

PIPE_PATH = r"\\.\pipe\NodeDeckKeePassBridge.v1"
APP_DATA = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "NodeDeckSSH"
PAIRING_FILE = APP_DATA / "pairing.bin"


class BridgeError(RuntimeError):
    pass


class KeePassBridge:
    def __init__(self):
        self._token = self._load_token()

    @staticmethod
    def _load_token() -> str:
        if not PAIRING_FILE.is_file():
            return ""
        try:
            import win32crypt
            return win32crypt.CryptUnprotectData(PAIRING_FILE.read_bytes(), None, None, None, 0)[1].decode("utf-8")
        except Exception:
            return ""

    @staticmethod
    def _save_token(token: str):
        import win32crypt
        APP_DATA.mkdir(parents=True, exist_ok=True)
        encrypted = win32crypt.CryptProtectData(token.encode("utf-8"), "NodeDeck SSH KeePass pairing", None, None, None, 0)
        PAIRING_FILE.write_bytes(encrypted)

    def paired_locally(self) -> bool:
        return bool(self._token)

    def request(self, op: str, **kwargs) -> dict:
        if os.name != "nt":
            raise BridgeError("KeePass köprüsü sadece Windows üzerinde çalışır.")
        try:
            import win32file
            import win32pipe
            import win32con
            import pywintypes
        except ImportError as exc:
            raise BridgeError("pywin32 kurulu değil.") from exc

        payload = {"op": op, "token": self._token, **kwargs}
        raw = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        handle = None
        try:
            win32pipe.WaitNamedPipe(PIPE_PATH, 1500)
            handle = win32file.CreateFile(
                PIPE_PATH, win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                0, None, win32con.OPEN_EXISTING, 0, None)
            win32file.WriteFile(handle, raw)
            output = bytearray()
            while b"\n" not in output:
                _, chunk = win32file.ReadFile(handle, 65536)
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > 1024 * 1024:
                    raise BridgeError("KeePass beklenenden büyük yanıt verdi.")
            if not output:
                raise BridgeError("KeePass köprüsü boş yanıt verdi.")
            reply = json.loads(bytes(output).split(b"\n", 1)[0].decode("utf-8"))
            if not reply.get("ok"):
                raise BridgeError(reply.get("error", "KeePass işlem hatası"))
            return reply
        except BridgeError:
            raise
        except Exception as exc:
            raise BridgeError("KeePass eklentisine erişilemiyor. KeePass 2 açık mı, eklenti kurulu mu? (%s)" % exc) from exc
        finally:
            if handle is not None:
                try:
                    win32file.CloseHandle(handle)
                except Exception:
                    pass

    def pair(self):
        reply = self.request("pair")
        token = reply["token"]
        self._save_token(token)
        self._token = token
        return True

    def status(self):
        return self.request("status")

    def entries(self):
        return self.request("list")["items"]

    def save(self, data: dict):
        return self.request("save", **data)

    def password(self, entry_id: str):
        return self.request("credential", id=entry_id)["password"]
