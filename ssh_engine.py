"""Paramiko SSH shell, strict host-key verification and terminal emulation."""
from __future__ import annotations

from preferences import tr

import base64
import codecs
import hashlib
from queue import Empty, SimpleQueue
import threading
import time
from pathlib import Path
from PySide6.QtCore import QObject, Signal
import paramiko

KNOWN_HOSTS = Path.home() / ".ssh" / "known_hosts"


class _AskHostKey(paramiko.MissingHostKeyPolicy):
    def __init__(self, owner):
        self.owner = owner

    def missing_host_key(self, client, hostname, key):
        fingerprint = base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode("ascii").rstrip("=")
        self.owner._hostkey_event.clear()
        self.owner._hostkey_approved = False
        self.owner.hostkey.emit(hostname, key.get_name(), "SHA256:" + fingerprint)
        if not self.owner._hostkey_event.wait(90) or not self.owner._hostkey_approved:
            raise paramiko.SSHException(tr("Sunucu anahtarı kullanıcı tarafından onaylanmadı."))
        KNOWN_HOSTS.parent.mkdir(parents=True, exist_ok=True)
        client.get_host_keys().add(hostname, key.get_name(), key)
        client.save_host_keys(str(KNOWN_HOSTS))


class SSHSession(QObject):
    output = Signal(str)
    connected = Signal()
    disconnected = Signal(str)
    hostkey = Signal(str, str, str)

    def __init__(self, hostname, port, username, password, cols=110, rows=34, *, keyfile=None, passphrase=None, agent=False, keepalive=20):
        super().__init__()
        self.hostname = hostname
        self.port = int(port)
        self.username = username
        self._password = password
        self._keyfile = keyfile
        self._passphrase = passphrase
        self._agent = agent
        self._keepalive = keepalive
        self._cols = cols
        self._rows = rows
        self._stopping = threading.Event()
        self._hostkey_event = threading.Event()
        self._hostkey_approved = False
        self.client = None
        self.channel = None
        self._commands = SimpleQueue()

    def approve_key(self, allow: bool):
        self._hostkey_approved = bool(allow)
        self._hostkey_event.set()

    def send(self, data: bytes):
        if not self._stopping.is_set():
            self._commands.put(("input", data))

    def resize(self, cols: int, rows: int):
        if not self._stopping.is_set():
            self._commands.put(("resize", (max(4, cols), max(2, rows))))

    def _handle_commands(self):
        for _ in range(32):
            try:
                command, value = self._commands.get_nowait()
            except Empty:
                return
            if command == "input":
                self.channel.sendall(value)
            else:
                cols, rows = value
                self.channel.resize_pty(width=cols, height=rows)

    def stop(self):
        self._stopping.set()
        self._hostkey_event.set()
        try:
            if self.channel: self.channel.close()
        except Exception:
            pass
        try:
            if self.client: self.client.close()
        except Exception:
            pass

    def run(self):
        reason = tr("Oturum kapatıldı")
        try:
            self.client = paramiko.SSHClient()
            KNOWN_HOSTS.parent.mkdir(parents=True, exist_ok=True)
            if KNOWN_HOSTS.exists():
                self.client.load_host_keys(str(KNOWN_HOSTS))
            self.client.set_missing_host_key_policy(_AskHostKey(self))
            try:
                self.client.connect(
                    hostname=self.hostname, port=self.port, username=self.username,
                    password=self._password, key_filename=self._keyfile, passphrase=self._passphrase,
                    look_for_keys=False, allow_agent=self._agent,
                    timeout=12, auth_timeout=15, banner_timeout=15)
            finally:
                self._password = None
                self._passphrase = None
            if self._stopping.is_set():
                return
            transport = self.client.get_transport()
            transport.set_keepalive(self._keepalive)
            self.channel = transport.open_session(timeout=12)
            self.channel.get_pty(term="xterm-256color", width=self._cols, height=self._rows)
            self.channel.invoke_shell()
            self.channel.settimeout(5)
            self.connected.emit()
            decoder = codecs.getincrementaldecoder("utf-8")("replace")
            while not self._stopping.is_set():
                self._handle_commands()
                if self.channel.recv_ready():
                    data = self.channel.recv(8192)
                    if not data:
                        break
                    decoded = decoder.decode(data)
                    if decoded:
                        self.output.emit(decoded)
                elif self.channel.exit_status_ready() or self.channel.closed:
                    break
                else:
                    time.sleep(0.035)
        except paramiko.AuthenticationException:
            reason = tr("Kimlik doğrulama başarısız. Kullanıcı ve kimlik doğrulama ayarlarını kontrol edin.")
        except paramiko.BadHostKeyException:
            reason = tr("GÜVENLİK: Sunucunun SSH anahtarı değişmiş! Bağlantı engellendi.")
        except Exception as exc:
            if not self._stopping.is_set():
                reason = str(exc)
        finally:
            self._password = None
            self.stop()
            self.disconnected.emit(reason)
