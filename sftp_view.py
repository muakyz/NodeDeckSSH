"""File browsing and transfers over an authenticated SSH transport."""
import errno
import os
import posixpath
import stat
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

import paramiko
from shiboken6 import isValid
from PySide6.QtWidgets import (
    QDialog, QInputDialog, QMenu, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QProgressBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)
from PySide6.QtCore import Qt, Signal
from preferences import tr


def sftp_operation(transport, operation):
    if not transport.is_active():
        raise RuntimeError("SSH oturumu kapalı.")
    channel = transport.open_session(timeout=12)
    try:
        channel.settimeout(30)
        channel.invoke_subsystem("sftp")
        with paramiko.SFTPClient(channel) as client:
            return operation(client)
    finally:
        channel.close()


def list_directory(client, path):
    path = client.normalize(path)
    entries = client.listdir_attr(path)
    rows = [(entry.filename, stat.S_ISDIR(entry.st_mode or 0), entry.st_size)
            for entry in entries if entry.filename not in (".", "..") and "/" not in entry.filename]
    return path, sorted(rows, key=lambda row: (not row[1], row[0].casefold()))


def download_file(client, remote, local, callback=None):
    with NamedTemporaryFile(dir=Path(local).parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        client.get(remote, str(temporary), callback=callback, prefetch=False)
        os.replace(temporary, local)
    finally:
        temporary.unlink(missing_ok=True)


def upload_file(client, local, remote, callback=None):
    try:
        client.lstat(remote)
    except OSError as error:
        if error.errno != errno.ENOENT:
            raise
    else:
        raise FileExistsError("Bu isimde bir uzak dosya zaten var.")
    temporary = posixpath.join(posixpath.dirname(remote), f".nodedeck-{uuid4().hex}.part")
    try:
        client.put(local, temporary, callback=callback)
        client.rename(temporary, remote)
    except Exception:
        try:
            client.remove(temporary)
        except OSError:
            pass
        raise


class SftpDialog(QDialog):
    transfer_progress = Signal(int, str)
    def __init__(self, parent, name, transport, run_job):
        super().__init__(parent)
        self.transport = transport
        self.run_job = run_job
        self.directory = "."
        self.busy = False
        self.setWindowTitle(f"SFTP · {name}")
        self.resize(720, 470)
        layout = QVBoxLayout(self)
        navigation = QHBoxLayout()
        self.path = QLineEdit(".")
        self.path.returnPressed.connect(self.navigate)
        navigation.addWidget(self.path, 1)
        go = QPushButton("Git")
        go.clicked.connect(self.navigate)
        navigation.addWidget(go)
        layout.addLayout(navigation)
        actions = QHBoxLayout()
        for label, action in (
            ("Üst klasör", lambda: self.browse(posixpath.dirname(self.directory))),
            ("Dosya yükle", self.upload),
            ("Dosya indir", self.download),
        ):
            button = QPushButton(label)
            button.clicked.connect(action)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.tree = QTreeWidget()
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.file_menu)
        self.setAcceptDrops(True)
        self.tree.setHeaderLabels(["Ad", "Tür", "Boyut (bayt)"])
        self.tree.setColumnWidth(0, 165)
        self.setMinimumWidth(250)
        self.tree.itemDoubleClicked.connect(self.open_item)
        layout.addWidget(self.tree)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.transfer_progress.connect(self.show_progress, Qt.ConnectionType.QueuedConnection)

    def show_progress(self, percent, label):
        if self.busy:
            self.progress.setValue(percent)
            self.status.setText(label)

    def reporter(self, label):
        previous = -1

        def report(done, total):
            nonlocal previous
            percent = min(99, int(done * 100 / total)) if total else 0
            if percent != previous:
                previous = percent
                if isValid(self):
                    self.transfer_progress.emit(percent, label)
        return report

    def begin_transfer(self, label):
        self.progress.setValue(0)
        self.progress.show()
        self.status.setText(label)

    def transfer_done(self, label):
        self.progress.setValue(100)
        self.status.setText(label)

    def start(self, operation, on_success, message):
        if self.busy:
            return
        self.busy = True
        self.status.setText(message)

        def success(value):
            self.busy = False
            if isValid(self):
                on_success(value)

        def failure(error):
            self.busy = False
            if isValid(self):
                self.progress.hide()
                self.status.setText(f"{tr('İşlem başarısız.')} {error}")

        self.run_job(lambda: sftp_operation(self.transport, operation), success, failure)

    def closeEvent(self, event):
        if self.busy:
            self.status.setText(tr("Dosya işlemi tamamlandıktan sonra pencereyi kapatabilirsiniz."))
            event.ignore()
            return
        super().closeEvent(event)

    def navigate(self):
        path = self.path.text().strip() or "."
        self.browse(posixpath.join(self.directory, path))

    def browse(self, path):
        self.start(lambda client: list_directory(client, path), self.show_directory, tr("Klasör okunuyor…"))

    def show_directory(self, result):
        self.directory, rows = result
        self.path.setText(self.directory)
        self.tree.clear()
        for name, folder, size in rows:
            item = QTreeWidgetItem([name, tr("Klasör") if folder else tr("Dosya"), "" if folder else str(size or 0)])
            item.setData(0, Qt.ItemDataRole.UserRole, folder)
            self.tree.addTopLevelItem(item)
        self.status.setText(tr("{count} öğe").format(count=len(rows)))

    def open_item(self, item, _column):
        if item.data(0, Qt.ItemDataRole.UserRole):
            self.browse(posixpath.join(self.directory, item.text(0)))
        else:
            self.download()

    def file_menu(self, pos):
        menu = QMenu(self)
        menu.addAction(tr("Yeni klasör"), self.mkdir)
        item = self.tree.itemAt(pos)
        if item:
            self.tree.setCurrentItem(item)
            menu.addAction(tr("Yeniden adlandır"), self.rename)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def remote_name(self, title, default=""):
        name, accepted = QInputDialog.getText(self, title, tr("Ad"), text=default)
        if accepted and name.strip() and name not in (".", "..") and "/" not in name and chr(0) not in name:
            return posixpath.join(self.directory, name)
        return None

    def mkdir(self):
        if self.busy:
            return
        path = self.remote_name(tr("Yeni klasör"))
        if path:
            self.start(lambda client: client.mkdir(path), lambda _: self.browse(self.directory), tr("Klasör oluşturuluyor…"))

    def rename(self):
        item = self.tree.currentItem()
        if self.busy or not item:
            return
        old = posixpath.join(self.directory, item.text(0))
        new = self.remote_name(tr("Yeniden adlandır"), item.text(0))
        if new and new != old:
            self.start(lambda client: client.rename(old, new), lambda _: self.browse(self.directory), tr("Yeniden adlandırılıyor…"))

    def dragEnterEvent(self, event):
        if not self.busy and event.mimeData().hasUrls() and all(
                url.isLocalFile() and Path(url.toLocalFile()).is_file() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths and not self.busy:
            self.upload_paths(paths)
            event.acceptProposedAction()

    def upload(self):
        if self.busy:
            return
        paths, _ = QFileDialog.getOpenFileNames(self, tr("Yüklenecek dosyalar"))
        if paths:
            self.upload_paths(paths)

    def upload_paths(self, paths):
        destination = self.directory

        self.begin_transfer("Uploading…")

        def transfer(client):
            sizes = [Path(local).stat().st_size for local in paths]
            total = sum(sizes)
            completed = 0
            for local, size in zip(paths, sizes):
                report = self.reporter(f"Uploading {Path(local).name}")
                upload_file(client, local, posixpath.join(destination, Path(local).name),
                            lambda sent, _total: report(completed + sent, total))
                completed += size
            return list_directory(client, destination)

        def done(result):
            self.show_directory(result)
            self.transfer_done("Upload complete.")

        self.start(transfer, done, "Uploading…")

    def download(self):
        if self.busy:
            return
        item = self.tree.currentItem()
        if not item or item.data(0, Qt.ItemDataRole.UserRole):
            self.status.setText(tr("İndirmek için bir dosya seçin."))
            return
        name = item.text(0)
        remote = posixpath.join(self.directory, name)
        local, _ = QFileDialog.getSaveFileName(self, tr("Dosyayı kaydet"), Path(name).name)
        if local:
            self.begin_transfer(f"Downloading {name}")
            report = self.reporter(f"Downloading {name}")
            self.start(lambda client: download_file(client, remote, local, report),
                       lambda _: self.transfer_done("Download complete."), f"Downloading {name}")
