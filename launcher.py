"""Entry point for the Windows bundle and its unattended startup test."""
import faulthandler
import os
import sys
import traceback
from pathlib import Path


def run():
    if "--smoke-test" not in sys.argv:
        from main import launch
        return launch()

    path = Path(os.environ["NODEDECK_SMOKE_LOG"])
    with path.open("w", encoding="utf-8", buffering=1) as log:
        sys.stdout = sys.stderr = log
        faulthandler.enable(log)
        try:
            print("Python bootloader started. Importing application.")
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
