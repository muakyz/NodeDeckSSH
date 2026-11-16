"""Embedded basic xterm screen. pyte handles cursor movement and ANSI control sequences."""
from __future__ import annotations

from preferences import tr

from collections import deque
import os
from PySide6.QtCore import QEvent, QRectF, Qt, Signal, QTimer
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPalette
from PySide6.QtWidgets import QApplication, QMenu, QPlainTextEdit, QSizePolicy
import pyte


class _HistoryScreen(pyte.Screen):
    def __init__(self, columns=110, lines=34):
        self.scrollback = deque(maxlen=2000)
        super().__init__(columns, lines)

    def index(self):
        top = self.margins.top if self.margins is not None else 0
        bottom = self.margins.bottom if self.margins is not None else self.lines - 1
        if top == 0 and bottom == self.lines - 1 and self.cursor.y == bottom:
            self.scrollback.append(self.display[0].rstrip())
        super().index()


class TerminalView(QPlainTextEdit):
    input_bytes = Signal(bytes)
    resized_grid = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Consolas" if os.name == "nt" else "Monospace", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setReadOnly(True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setMinimumSize(75, 45)
        self._live = False
        self._blink_enabled = True
        self._blink_on = True
        self._cursor_row = 0
        self._cursor_prefix = ""
        self._blink = QTimer(self)
        self._blink.setInterval(500)
        self._blink.timeout.connect(self._toggle_cursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setObjectName("Terminal")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self._screen = _HistoryScreen(110, 34)
        self._stream = pyte.Stream(self._screen)
        self._pending = ""
        self._changed = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._render)
        self._timer.start(65)
        self._last_cols = 110
        self._last_rows = 34
        self.setPlainText(tr("Bağlanıyor…"))

    def feed(self, text: str):
        try:
            self._stream.feed(text)
            self._changed = True
        except Exception:
            self._pending += text
            self._changed = True

    def set_live(self, live):
        self._live = live
        self._blink_on = True
        if live:
            if self._blink_enabled:
                self._blink.start()
            self._changed = True
        else:
            self._blink.stop()
        self.viewport().update()

    def configure(self, settings):
        font = self.font()
        font.setFamily(settings.value("terminal/font", font.family(), type=str))
        font.setPointSize(settings.value("terminal/size", 10, type=int))
        self.setFont(font)
        self._blink_enabled = settings.value("terminal/blink", True, type=bool)
        self._blink.stop()
        self.set_live(self._live)
        self._resize_grid()

    def _toggle_cursor(self):
        self._blink_on = not self._blink_on
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if (not self._live or self._screen.cursor.hidden or self.textCursor().hasSelection()
                or (self.hasFocus() and not self._blink_on)):
            return
        block = self.document().findBlockByNumber(self._cursor_row)
        if not block.isValid():
            return
        rect = self.blockBoundingGeometry(block).translated(self.contentOffset())
        line = block.layout().lineAt(0)
        if not line.isValid():
            return
        metrics = QFontMetrics(self.font())
        x = rect.left() + line.x() + metrics.horizontalAdvance(self._cursor_prefix)
        y = rect.top() + line.y() + line.height() - 2
        painter = QPainter(self.viewport())
        painter.fillRect(QRectF(x, y, metrics.horizontalAdvance("M"), 2),
                         self.palette().color(QPalette.ColorRole.Text))

    def _render(self):
        if not self._changed or self.textCursor().hasSelection():
            return
        self._changed = False
        bar = self.verticalScrollBar()
        position = bar.value()
        at_bottom = position >= bar.maximum() - 2
        history = list(self._screen.scrollback)[-500:]
        cursor = self._screen.cursor
        screen_lines = [line.rstrip() for line in self._screen.display]
        line_buffer = self._screen.buffer.get(cursor.y, {})
        self._cursor_prefix = "".join(
            line_buffer[col].data if col in line_buffer else " "
            for col in range(cursor.x)
        )
        self._cursor_row = len(history) + cursor.y
        end = max(cursor.y + 1, max((i + 1 for i, row in enumerate(screen_lines) if row), default=0))
        data = "\n".join(history + screen_lines[:end]) + self._pending
        if data != self.toPlainText():
            self.setPlainText(data)
        bar.setValue(bar.maximum() if at_bottom else position)
        self.viewport().update()

    def grid_size(self):
        return self._last_cols, self._last_rows

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_grid()

    def _resize_grid(self):
        fm = QFontMetrics(self.font())
        width = max(1, fm.horizontalAdvance("M"))
        height = max(1, fm.lineSpacing())
        cols = max(4, (self.viewport().width() - 16) // width)
        rows = max(2, (self.viewport().height() - 10) // height)
        if (cols, rows) != (self._last_cols, self._last_rows):
            self._last_cols, self._last_rows = cols, rows
            self._screen.resize(rows, cols)
            self.resized_grid.emit(cols, rows)
            self._changed = True

    def event(self, event):
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self.input_bytes.emit(b"\x1b[Z" if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else b"\t")
            return True
        return super().event(event)

    def keyPressEvent(self, ev):
        mod = ev.modifiers()
        key = ev.key()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return
        ctrl = bool(mod & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mod & Qt.KeyboardModifier.ShiftModifier)
        if ctrl and key == Qt.Key.Key_C and (shift or self.textCursor().hasSelection()):
            self.copy()
            return
        if (ctrl and key == Qt.Key.Key_V) or (shift and key == Qt.Key.Key_Insert):
            self.paste()
            return
        if ctrl and key == Qt.Key.Key_Insert:
            self.copy()
            return
        codes = {
            Qt.Key.Key_Return: b"\r", Qt.Key.Key_Enter: b"\r",
            Qt.Key.Key_Backspace: b"\x7f", Qt.Key.Key_Tab: b"\t",
            Qt.Key.Key_Escape: b"\x1b", Qt.Key.Key_Up: b"\x1b[A",
            Qt.Key.Key_Down: b"\x1b[B", Qt.Key.Key_Right: b"\x1b[C",
            Qt.Key.Key_Left: b"\x1b[D", Qt.Key.Key_Home: b"\x1b[H",
            Qt.Key.Key_End: b"\x1b[F", Qt.Key.Key_Delete: b"\x1b[3~",
            Qt.Key.Key_PageUp: b"\x1b[5~", Qt.Key.Key_PageDown: b"\x1b[6~",
            Qt.Key.Key_F1: b"\x1bOP", Qt.Key.Key_F2: b"\x1bOQ",
            Qt.Key.Key_F3: b"\x1bOR", Qt.Key.Key_F4: b"\x1bOS",
        }
        if self.textCursor().hasSelection() and self._live:
            cursor = self.textCursor()
            cursor.clearSelection()
            self.setTextCursor(cursor)
        self._blink_on = True
        self.viewport().update()
        if ctrl and Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            self.input_bytes.emit(bytes([key - Qt.Key.Key_A + 1]))
            return
        if key in codes:
            self.input_bytes.emit(codes[key])
            return
        if ev.text():
            self.input_bytes.emit(ev.text().encode("utf-8"))

    def paste(self):
        text = QApplication.clipboard().text()
        if self._live and text:
            cursor = self.textCursor()
            cursor.clearSelection()
            self.setTextCursor(cursor)
            text = text.replace("\r\n", "\n").replace("\n", "\r").replace("\x00", "")
            self.input_bytes.emit(text.encode("utf-8"))
            self.setFocus()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        copy = menu.addAction(tr("Kopyala"), self.copy)
        copy.setEnabled(self.textCursor().hasSelection())
        paste = menu.addAction(tr("Yapıştır"), self.paste)
        paste.setEnabled(self._live and bool(QApplication.clipboard().text()))
        menu.addAction(tr("Tümünü seç"), self.selectAll)
        menu.exec(event.globalPos())
