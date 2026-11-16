"""Read legacy DPAPI passwords during local vault migration."""
from base64 import b64decode


def unprotect(value):
    import win32crypt

    _, data = win32crypt.CryptUnprotectData(b64decode(value, validate=True), None, None, None, 1)
    return data.decode("utf-8")
