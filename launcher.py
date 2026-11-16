"""Entry point for the Windows bundle and its unattended startup test."""
import faulthandler
import os
import sys
import traceback
from pathlib import Path


def load_windows_runtime(log=None):
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return
    from ctypes import WinDLL

    bundle = Path(sys._MEIPASS)
    for name in ("vcruntime140.dll", "python3.dll"):
        library = bundle / name
        if not library.is_file():
            raise FileNotFoundError(f"Missing packaged runtime: {name}")
        try:
            WinDLL(str(library))
        except OSError as error:
            raise RuntimeError(f"Windows could not load {name}: {error}") from error
        if log:
            print(f"Loaded packaged runtime: {name}", file=log, flush=True)
    if log:
        import _argon2_cffi_bindings
        print(f"Loaded Argon2 extension: {_argon2_cffi_bindings.__file__}", file=log, flush=True)


def run():
    if "--smoke-test" not in sys.argv:
        load_windows_runtime()
        from main import launch
        return launch()

    path = Path(os.environ["NODEDECK_SMOKE_LOG"])
    with path.open("w", encoding="utf-8", buffering=1) as log:
        sys.stdout = sys.stderr = log
        faulthandler.enable(log)
        try:
            print("Python bootloader started. Importing application.")
            load_windows_runtime(log)
            from main import launch
            from PySide6.QtCore import qInstallMessageHandler

            def report_qt(_level, _context, message):
                print(f"Qt: {message}", flush=True)

            qInstallMessageHandler(report_qt)
            print("Imports complete. Starting Qt.")
            result = launch()
            if result == 0:
                print("NODEDECK_SMOKE_OK")
            return result
        except Exception:
            traceback.print_exc()
            return 1
        finally:
            faulthandler.disable()


if __name__ == "__main__":
    sys.exit(run())
