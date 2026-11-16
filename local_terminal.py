"""Interactive Windows console hosted in the embedded terminal."""
from preferences import tr
import os
from PySide6.QtCore import QObject, Signal


class LocalTerminal(QObject):
    output = Signal(str)
    connected = Signal()
    disconnected = Signal(str)

    def __init__(self, cols, rows):
        super().__init__()
        self.dimensions = (rows, cols)
        self.process = None
        self.stopping = False

    def run(self):
        reason = tr("Yerel terminal kapandı.")
        try:
            if self.stopping:
                return
            from winpty import PtyProcess
            self.process = PtyProcess.spawn(
                [os.environ.get("COMSPEC", "cmd.exe")], dimensions=self.dimensions,
            )
            if self.stopping:
                self.process.close()
                return
            self.connected.emit()
            while not self.stopping:
                data = self.process.read(4096)
                if data:
                    self.output.emit(data)
                elif not self.process.isalive():
                    break
        except EOFError:
            pass
        except Exception as error:
            if not self.stopping:
                reason = str(error)
        finally:
            self.stop()
            self.disconnected.emit(reason)

    def send(self, data):
        if self.process is not None and not self.stopping:
            try:
                self.process.write(data.decode("utf-8"))
            except (OSError, EOFError, RuntimeError):
                pass

    def resize(self, cols, rows):
        self.dimensions = (rows, cols)
        if self.process is not None and not self.stopping:
            try:
                self.process.setwinsize(rows, cols)
            except (OSError, EOFError, RuntimeError):
                pass

    def stop(self):
        if self.stopping:
            return
        self.stopping = True
        if self.process is not None:
            try:
                self.process.close()
            except (OSError, EOFError, RuntimeError):
                pass
