from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QAbstractItemView, QTreeWidget


class ServerTree(QTreeWidget):
    move_requested = Signal(str, str)
    mime_type = "application/x-nodedeck-profile"

    def __init__(self):
        super().__init__()
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDropIndicatorShown(False)

    def startDrag(self, _actions):
        item = self.currentItem()
        identifier = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if identifier:
            data = QMimeData()
            data.setData(self.mime_type, identifier.encode("utf-8"))
            drag = QDrag(self)
            drag.setMimeData(data)
            drag.exec(Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event):
        if event.source() is self and event.mimeData().hasFormat(self.mime_type):
            event.acceptProposedAction()
        else:
            event.ignore()

    def destination(self, event):
        item = self.itemAt(event.position().toPoint())
        return item.data(0, Qt.ItemDataRole.UserRole + 1) if item else None

    def dragMoveEvent(self, event):
        if event.source() is self and self.destination(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        path = self.destination(event)
        if event.source() is self and path and event.mimeData().hasFormat(self.mime_type):
            identifier = bytes(event.mimeData().data(self.mime_type)).decode("utf-8")
            self.move_requested.emit(identifier, path)
            event.acceptProposedAction()
        else:
            event.ignore()
