"""Short selection transition for the workspace tab bar."""
from PySide6.QtCore import QEasingCurve, QRectF, QVariantAnimation
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QTabBar


class WorkspaceTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setExpanding(False)
        self.animated = True
        self._indicator = QRectF()
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(135)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._update_indicator)
        self.currentChanged.connect(self._move_indicator)
        self.tabMoved.connect(self._reset_indicator)

    def _target(self, index):
        rect = self.tabRect(index)
        return QRectF(rect.x() + 9, rect.bottom() - 1, max(0, rect.width() - 18), 2)

    def _update_indicator(self, rect):
        self._indicator = rect
        self.update()

    def _move_indicator(self, index):
        self._animation.stop()
        if index < 0:
            self._update_indicator(QRectF())
        elif not self.animated or self._indicator.isEmpty() or not self.isVisible():
            self._update_indicator(self._target(index))
        else:
            self._animation.setStartValue(self._indicator)
            self._animation.setEndValue(self._target(index))
            self._animation.start()

    def _reset_indicator(self, *_):
        self._animation.stop()
        self._update_indicator(self._target(self.currentIndex()) if self.currentIndex() >= 0 else QRectF())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reset_indicator()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.currentIndex() < 0:
            return
        rect = self._indicator if self._animation.state() == QVariantAnimation.State.Running else self._target(self.currentIndex())
        painter = QPainter(self)
        painter.fillRect(rect, QColor("#e7b479"))
