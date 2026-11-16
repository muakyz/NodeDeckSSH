"""Local password vault using libsodium Argon2id and SecretBox."""
import base64
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from nacl import exceptions, pwhash, secret, utils

from bridge_client import APP_DATA

VAULT_FILE = APP_DATA / "password-vault.json"
PREFIX = "vault1:"
CHECK = b"NodeDeckSSH password vault v1"


def encode(value):
    return base64.b64encode(value).decode("ascii")


def decode(value):
    return base64.b64decode(value, validate=True)


class PasswordVault:
    def __init__(self):
        self._box = None

    @property
    def unlocked(self):
        return self._box is not None

    @property
    def exists(self):
        return VAULT_FILE.exists()

    def lock(self):
        self._box = None

    def unlock(self, password, *, create=False):
        self.lock()
        if create:
            if len(password) < 12:
                raise ValueError("Use a master password of at least 12 characters.")
            salt = utils.random(pwhash.argon2id.SALTBYTES)
        else:
            try:
                data = json.loads(VAULT_FILE.read_text(encoding="utf-8"))
                if data["version"] != 1:
                    raise ValueError()
                salt = decode(data["salt"])
                check = decode(data["check"])
                if len(salt) != pwhash.argon2id.SALTBYTES:
                    raise ValueError()
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise ValueError("Could not read the local vault header.") from error
        box = secret.SecretBox(pwhash.argon2id.kdf(
            secret.SecretBox.KEY_SIZE, password.encode("utf-8"), salt,
            opslimit=pwhash.argon2id.OPSLIMIT_INTERACTIVE,
            memlimit=pwhash.argon2id.MEMLIMIT_INTERACTIVE,
        ))
        if create:
            VAULT_FILE.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with NamedTemporaryFile(dir=VAULT_FILE.parent, delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(json.dumps({
                        "version": 1, "salt": encode(salt), "check": encode(box.encrypt(CHECK)),
                    }).encode("ascii"))
                # Publish a complete file without replacing another instance's vault.
                os.link(temporary, VAULT_FILE)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        else:
            try:
                if box.decrypt(check) != CHECK:
                    raise exceptions.CryptoError()
            except (exceptions.CryptoError, ValueError) as error:
                raise ValueError("Incorrect master password or damaged vault header.") from error
        self._box = box

    def encrypt(self, profile_id, password):
        if not self.unlocked:
            raise ValueError("Unlock the local vault first.")
        payload = json.dumps([profile_id, password], ensure_ascii=False).encode("utf-8")
        return PREFIX + encode(self._box.encrypt(payload))

    def decrypt(self, profile_id, value):
        if not self.unlocked:
            raise ValueError("Unlock the local vault first.")
        try:
            if not value.startswith(PREFIX):
                raise ValueError()
            stored_id, password = json.loads(self._box.decrypt(decode(value.removeprefix(PREFIX))))
            if stored_id != profile_id or not isinstance(password, str):
                raise ValueError()
            return password
        except (exceptions.CryptoError, ValueError, TypeError) as error:
            raise ValueError("The saved password is corrupt or belongs to another profile.") from error


def migrate_profiles(profiles, vault, legacy_decrypt):
    """Return a complete migrated snapshot, or leave the original snapshot intact."""
    return [
        {**profile, "protected_password": vault.encrypt(profile["id"], legacy_decrypt(value))}
        if (value := profile.get("protected_password")) and not value.startswith(PREFIX)
        else profile
        for profile in profiles
    ]
