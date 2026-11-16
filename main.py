"""NodeDeck SSH — Windows SSH connection manager with manual, KeePassXC and KeePass 2 authentication.

Run: python main.py    |    Build: build_windows.bat
"""
from __future__ import annotations

import os
import sys
import time
from functools import partial
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt, QObject, Signal, QRunnable, QThreadPool, QThread, QTimer, QSize, Slot, QSettings, QUrl
from PySide6.QtGui import QIcon, QFont, QKeySequence, QShortcut, QPalette, QColor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QLineEdit, QTreeWidget, QTreeWidgetItem, QTabWidget,
    QSplitter, QStackedWidget, QFormLayout, QDialog, QDialogButtonBox,
    QSpinBox, QMenu, QMessageBox, QSizePolicy, QStatusBar, QComboBox,
    QAbstractItemView, QStyle, QFileDialog, QInputDialog, QCheckBox
)

from bridge_client import KeePassBridge
from keepassxc_client import find_cli, read_password
from local_profiles import load_profiles, save_profiles
from manual_passwords import unprotect
from password_vault import PREFIX, PasswordVault, migrate_profiles
from xc_vault import load_ssh_hub, save_ssh_hub_entry
from profile_backup import export_backup, read_backup, restore_backup
from release_updates import DEFAULT_FEED_URL, VERSION, check_release
from sftp_view import SftpDialog
from preferences import Preferences, apply_preferences, localize, tr
from server_tree import ServerTree
from local_terminal import LocalTerminal
import folders
from ssh_engine import SSHSession
from terminal_view import TerminalView
from workspace_tabs import WorkspaceTabBar

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
STYLE_FILE = BASE / "assets" / "style.qss"
ICON_FILE = BASE / "assets" / "nodedeck.ico"


class AsyncSignals(QObject):
    result = Signal(object)


class AsyncJob(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = AsyncSignals()

    def run(self):
        try:
            value = self.fn()
            self.signals.result.emit((True, value))
        except Exception as exc:
            self.signals.result.emit((False, str(exc)))
        finally:
            self.fn = None


class NodeForm(QDialog):
    def __init__(self, parent=None, item=None, existing_groups=(), source="keepass", default_group=""):
        super().__init__(parent)
        self.editing = item is not None
        self.item = item or {}
        self.source = source
        self.setWindowTitle("Sunucuyu düzenle" if self.editing else "Yeni SSH bağlantısı")
        self.setMinimumWidth(460)
        self.setModal(True)
        self.setObjectName("NodeForm")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(18)
        caption = QLabel({
            "manual": "SSH parolası her bağlantıda sorulur.",
            "xc": "SSH parolası seçilen KeePassXC kaydından alınır.",
            "keepass": "Bağlantı bilgileri doğrudan KeePass veritabanına kaydedilir.",
            "hub": "Save to the selected KeePassXC vault.",
        }[source])
        caption.setObjectName("Muted")
        caption.setWordWrap(True)
        layout.addWidget(caption)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setHorizontalSpacing(22)
        form.setVerticalSpacing(14)
        self.name = QLineEdit(self.item.get("name", ""))
        self.name.setPlaceholderText(tr("Örn. Proxmox / WEB-01"))
        self.hostname = QLineEdit(self.item.get("host", ""))
        self.hostname.setPlaceholderText("192.168.1.10 veya sunucu.local")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(int(self.item.get("port", 22)))
        self.username = QLineEdit(self.item.get("username", ""))
        self.username.setPlaceholderText("root / Administrator")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText(tr("Değiştirmemek için boş bırakın") if self.editing else tr("KeePass içinde şifreli saklanır"))
        self.group = QComboBox()
        self.group.setEditable(True)
        self.group.lineEdit().setPlaceholderText("Optional folder")
        for g in sorted(set(["Genel", "Linux", "Windows", "Ağ Cihazları", *existing_groups]), key=str.casefold):
            self.group.addItem(g)
        self.group.setCurrentText(self.item.get("group", default_group))
        for key, widget in [
            ("Bağlantı adı", self.name), ("Sunucu / IP", self.hostname),
            ("SSH portu", self.port), ("Kullanıcı", self.username),
            ("Grup", self.group)
        ]:
            form.addRow(key, widget)
        self.forget_password = QCheckBox("Kayıtlı parolayı sil", self)
        self.forget_password.hide()
        if source in ("keepass", "manual", "hub"):
            form.addRow(tr("Parola"), self.password)
            if source == "manual":
                self.password.setPlaceholderText(tr("İsteğe bağlı · boşsa bağlantıda sorulur"))
                if self.item.get("protected_password"):
                    self.password.setPlaceholderText(tr("Kayıtlı parolayı korumak için boş bırakın"))
                    form.addRow(self.forget_password)
                    self.forget_password.show()
        else:
            self.password.hide()
        self.auth = QComboBox()
        for label, value in (("Parola", "password"), ("OpenSSH anahtarı", "key"), ("SSH agent", "agent")):
            self.auth.addItem(label, value)
        self.auth.setCurrentIndex(max(0, self.auth.findData(self.item.get("auth", "password"))))
        self.ssh_key = QLineEdit(self.item.get("ssh_key", ""), self)
        self.ssh_key.hide()
        if source == "manual":
            form.addRow("Kimlik doğrulama", self.auth)
            key_row = self.file_field(self.ssh_key, "Tüm dosyalar (*)")
            self.ssh_key.show()
            form.addRow("SSH özel anahtar dosyası", key_row)
            password_label = form.labelForField(self.password)
            key_label = form.labelForField(key_row)

            def update_auth():
                mode = self.auth.currentData()
                for widget in (self.password, password_label):
                    widget.setVisible(mode == "password")
                key_row.setVisible(mode == "key")
                key_label.setVisible(mode == "key")
                self.forget_password.setVisible(mode == "password" and bool(self.item.get("protected_password")))

            self.auth.currentIndexChanged.connect(update_auth)
            update_auth()
        self.database = QLineEdit(self.item.get("database", ""))
        self.xc_entry = QLineEdit(self.item.get("xc_entry", ""))
        self.key_file = QLineEdit(self.item.get("key_file", ""))
        if source == "xc":
            form.addRow("Kasa (.kdbx)", self.file_field(self.database, tr("KeePass kasası (*.kdbx)")))
            self.xc_entry.setPlaceholderText("SSH Hub/Linux/Proxmox")
            form.addRow(tr("Kayıt yolu"), self.xc_entry)
            form.addRow(tr("Anahtar dosyası (varsa)"), self.file_field(self.key_file, "Tüm dosyalar (*)"))
        else:
            for field in (self.database, self.xc_entry, self.key_file):
                field.setParent(self)
                field.hide()
        layout.addLayout(form)
        self.message = QLabel("")
        self.message.setObjectName("ErrorText")
        layout.addWidget(self.message)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("KeePass'e kaydet" if source == "keepass" else "Profili kaydet")
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("Primary")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Vazgeç")
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def file_field(self, field, file_filter):
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        browse = QPushButton("Gözat…")
        layout.addWidget(field)
        layout.addWidget(browse)

        def choose():
            filename, _ = QFileDialog.getOpenFileName(self, tr("Dosya seç"), field.text(), file_filter)
            if filename:
                field.setText(filename)

        browse.clicked.connect(choose)
        return row

    def validate_and_accept(self):
        if not all([self.name.text().strip(), self.hostname.text().strip(), self.username.text().strip()]):
            self.message.setText("Name, host and username are required.")
            return
        if " " in self.hostname.text().strip():
            self.message.setText(tr("IP / sunucu adında boşluk olamaz."))
            return
        if self.source == "xc":
            database = self.database.text().strip()
            key_file = self.key_file.text().strip()
            if not database or not Path(database).is_file() or not self.xc_entry.text().strip():
                self.message.setText(tr("Mevcut bir KDBX dosyası ve kayıt yolu girin."))
                return
            if key_file and not Path(key_file).is_file():
                self.message.setText(tr("Anahtar dosyası bulunamadı."))
                return
        if self.source == "manual" and self.auth.currentData() == "key" and not Path(self.ssh_key.text()).is_file():
            self.message.setText(tr("Geçerli bir SSH özel anahtar dosyası seçin."))
            return
        self.accept()

    def values(self):
        return {
            "id": self.item.get("id", ""), "name": self.name.text().strip(),
            "host": self.hostname.text().strip(), "port": str(self.port.value()),
            "username": self.username.text().strip(), "password": self.password.text(),
            "group": self.group.currentText().strip(), "source": self.source,
            "database": self.database.text().strip(), "xc_entry": self.xc_entry.text().strip(),
            "key_file": self.key_file.text().strip(),
            "forget_password": self.forget_password.isChecked(),
            "auth": self.auth.currentData(), "ssh_key": self.ssh_key.text().strip(),
        }


class SessionPane(QWidget):
    close_requested = Signal()
    sftp_requested = Signal()
    ready_for_sftp = Signal()

    def __init__(self, entry):
        super().__init__()
        self.entry = entry
        self.connected = False
        self.open_sftp_on_connect = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        top = QFrame()
        top.setObjectName("SessionHeader")
        row = QHBoxLayout(top)
        row.setContentsMargins(10, 5, 6, 5)
        row.setSpacing(7)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        title = QLabel(entry["name"])
        title.setObjectName("PaneTitle")
        detail = QLabel(f'{entry["username"]}@{entry["host"]}:{entry["port"]}' if entry["username"] else entry["host"])
        detail.setObjectName("Muted")
        texts.addWidget(title)
        texts.addWidget(detail)
        for label in (title, detail):
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            label.setToolTip(label.text())
        row.addLayout(texts, 1)
        self.state = QLabel("Bağlanıyor…")
        self.state.setObjectName("ConnectionState")
        row.addWidget(self.state)
        self.broadcast_target = QCheckBox("Toplu")
        self.broadcast_target.setToolTip(tr("Bu oturumu toplu komuta dahil et"))
        self.broadcast_target.setEnabled(False)
        row.addWidget(self.broadcast_target)
        self.sftp_button = QPushButton("SFTP")
        self.sftp_button.setEnabled(False)
        self.sftp_button.clicked.connect(self.sftp_requested.emit)
        row.addWidget(self.sftp_button)
        button = QPushButton("Kapat")
        button.setObjectName("SubtleButton")
        button.clicked.connect(self.close_requested.emit)
        row.addWidget(button)
        self.reconnect = QPushButton("Yeniden bağlan")
        self.reconnect.hide()
        row.addWidget(self.reconnect)
        layout.addWidget(top)
        self.terminal = TerminalView()
        self.content = QSplitter(Qt.Orientation.Horizontal)
        self.content.addWidget(self.terminal)
        self.content.setChildrenCollapsible(False)
        self.content.setHandleWidth(4)
        self.sftp_panel = None
        layout.addWidget(self.content, 1)

    def set_state(self, text, state):
        self.state.setText(text)
        self.state.setProperty("state", state)
        self.state.style().unpolish(self.state)
        self.state.style().polish(self.state)
        self.state.setProperty("original_text", text)
        localize(self.state)

    def set_connected(self):
        self.connected = True
        self.terminal.set_live(True)
        self.sftp_button.setEnabled(True)
        self.broadcast_target.setEnabled(True)
        self.set_state("● Bağlı", "connected")
        self.terminal.setFocus()
        if self.open_sftp_on_connect:
            self.open_sftp_on_connect = False
            self.ready_for_sftp.emit()

    def set_disconnected(self, reason):
        self.connected = False
        self.terminal.set_live(False)
        self.sftp_button.setEnabled(False)
        if self.sftp_panel:
            self.sftp_panel.hide()
        self.broadcast_target.setChecked(False)
        self.broadcast_target.setEnabled(False)
        self.set_state("Kapalı", "closed")
        self.reconnect.setVisible(bool(self.entry["username"]))
        self.terminal.feed("\r\n\n[ NodeDeck ] " + reason + "\r\n")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.bridge = KeePassBridge()
        self.items = []
        self.local_profiles = []
        self.password_vault = PasswordVault()
        self.vault_busy = False
        self.clipboard_password = None
        self.vault_items = []
        self.hub_items = []
        self.hub_passwords = {}
        self.hub_credentials = None
        self.settings = QSettings("NodeDeck", "NodeDeck SSH")
        self.hub_stamp = None
        self.hub_loading = False
        self.groups = {}
        self.session_views = []
        self.split_groups = []
        self.folder_paths, self.locations = [], {}
        self.folder_error = False
        try:
            self.folder_paths, self.locations = folders.load()
        except (OSError, ValueError, KeyError, TypeError):
            self.folder_error = True
        self.panes = {}  # SessionPane -> (QThread, SSHSession)
        self.pool = QThreadPool.globalInstance()
        self.jobs = {}
        self.is_unlocked = False
        self.is_paired = False
        self._checking = False
        self._list_refreshing = False
        self._last_list = 0.0
        self._last_good_state = False
        self.closing = False
        self._make_ui()
        localize(self)
        self._make_shortcuts()
        try:
            self.local_profiles = load_profiles()
        except (OSError, ValueError):
            self.add_btn.setToolTip(tr("Yerel profil dosyası okunamadı."))
            QMessageBox.warning(self, tr("Yerel profiller"), tr("Profil dosyası okunamadı. Dosya düzeltilene kadar yerel kayıtlar değiştirilemez."))
        self.update_items()
        self.check_status()
        self.poll = QTimer(self)
        self.poll.timeout.connect(self.check_status)
        self.poll.start(3000)
        self.poll.timeout.connect(self.refresh_hub)
        self.update_busy = False
        if self.settings.value("updates/startup", True, type=bool):
            QTimer.singleShot(1500, lambda: self.check_updates(silent=True))

    def _make_ui(self):
        self.resize(1280, 800)
        self.setMinimumSize(880, 580)
        self.setWindowTitle(f"NodeDeck SSH {VERSION}")
        if ICON_FILE.exists():
            self.setWindowIcon(QIcon(str(ICON_FILE)))
        root = QWidget()
        root.setObjectName("MainRoot")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        top = QFrame()
        top.setObjectName("TopBar")
        head = QHBoxLayout(top)
        head.setContentsMargins(14, 0, 14, 0)
        head.setSpacing(8)
        brand_icon = QLabel()
        brand_icon.setPixmap(QIcon(str(ICON_FILE)).pixmap(22, 22))
        head.addWidget(brand_icon)
        brand = QLabel("NodeDeck SSH")
        brand.setObjectName("Brand")
        head.addWidget(brand)
        head.addStretch()
        self.keepass_badge = QLabel("KeePass 2 kontrol ediliyor…")
        self.keepass_badge.setObjectName("KeePassBadge")
        head.addWidget(self.keepass_badge)
        self.pair_btn = QPushButton("KeePass ile eşleştir")
        self.pair_btn.setObjectName("Secondary")
        self.pair_btn.clicked.connect(self.on_pair)
        self.pair_btn.setVisible(False)
        head.addWidget(self.pair_btn)
        self.hub_btn = QPushButton("KeePassXC kasasını aç")
        self.hub_btn.setObjectName("Secondary")
        self.hub_btn.clicked.connect(self.toggle_hub)
        head.addWidget(self.hub_btn)
        self.refresh_btn = QPushButton("Yenile")
        self.refresh_btn.setObjectName("Secondary")
        self.refresh_btn.clicked.connect(self.refresh_sources)
        head.addWidget(self.refresh_btn)
        self.add_btn = QPushButton("+  Yeni sunucu")
        self.add_btn.setObjectName("Primary")
        self.add_btn.clicked.connect(self.add_server)
        head.addWidget(self.add_btn)
        self.local_vault_btn = QPushButton("Unlock local vault")
        self.local_vault_btn.clicked.connect(self.toggle_local_vault)
        head.addWidget(self.local_vault_btn)
        settings_btn = QPushButton("Ayarlar")
        settings_btn.clicked.connect(self.open_preferences)
        head.addWidget(settings_btn)
        top.setFixedHeight(52)
        outer.addWidget(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(4)
        outer.addWidget(splitter, 1)
        left = QFrame()
        left.setObjectName("Sidebar")
        left.setMinimumWidth(165)
        side = QVBoxLayout(left)
        side.setContentsMargins(10, 11, 10, 0)
        side.setSpacing(8)
        group_label = QLabel("Sunucular")
        group_label.setObjectName("SectionTitle")
        side.addWidget(group_label)
        folder_bar = QHBoxLayout()
        folder_button = QPushButton("+ Klasör")
        folder_button.clicked.connect(self.create_selected_folder)
        folder_bar.addWidget(folder_button)
        terminal_button = QPushButton("+ Terminal")
        terminal_button.clicked.connect(self.open_local_terminal)
        folder_bar.addWidget(terminal_button)
        side.addLayout(folder_bar)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Sunucu ara...  Ctrl+K")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.populate_tree)
        side.addWidget(self.search)
        self.tree = ServerTree()
        self.tree.move_requested.connect(self.place_profile)
        self.tree.setHeaderLabels(["Sunucu", "Adres"])
        self.tree.setColumnWidth(0, 155)
        self.tree.setIndentation(15)
        self.tree.setRootIsDecorated(True)
        self.tree.setAnimated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.itemDoubleClicked.connect(self.tree_double_click)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.tree_menu)
        self.empty_servers = QPushButton("No servers · Add a server")
        self.empty_servers.clicked.connect(lambda: self.add_server(""))
        side.addWidget(self.empty_servers)
        side.addWidget(self.tree, 1)
        under = QFrame()
        under.setObjectName("AsideFoot")
        foot = QVBoxLayout(under)
        foot.setContentsMargins(3, 7, 3, 7)
        foot.setSpacing(3)
        self.device_count = QLabel("0 sunucu")
        self.device_count.setObjectName("FootMetric")
        foot.addWidget(self.device_count)
        side.addWidget(under)
        splitter.addWidget(left)

        workspace = QFrame()
        workspace.setObjectName("Workspace")
        stage = QVBoxLayout(workspace)
        stage.setContentsMargins(0, 0, 0, 0)
        stage.setSpacing(0)
        stage_head = QFrame()
        stage_head.setObjectName("StageHeader")
        hh = QHBoxLayout(stage_head)
        hh.setContentsMargins(10, 6, 10, 6)
        split_button = QPushButton("Oturumları böl…")
        split_button.clicked.connect(self.choose_split)
        hh.addWidget(split_button)
        separate_button = QPushButton("Sekmelere ayır")
        separate_button.clicked.connect(self.separate_current)
        hh.addWidget(separate_button)
        hh.addStretch()
        self.hint = QLabel(tr("Bir sunucuyu çift tıklayarak bağlan"))
        self.hint.setObjectName("Muted")
        hh.addWidget(self.hint)
        stage.addWidget(stage_head)
        self.pages = QStackedWidget()
        self.empty = QWidget()
        self.empty.setObjectName("EmptyWorkspace")
        empty_l = QVBoxLayout(self.empty)
        empty_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_l.setSpacing(12)
        self.empty_title = QLabel("Açık oturum yok")
        self.empty_title.setObjectName("EmptyTitle")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_l.addWidget(self.empty_title)
        self.empty_detail = QLabel("Bağlanmak için listeden bir sunucuya çift tıkla.")
        self.empty_detail.setObjectName("EmptyDetail")
        self.empty_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_detail.setWordWrap(True)
        self.empty_detail.setMaximumWidth(560)
        empty_l.addWidget(self.empty_detail)
        open_terminal = QPushButton("Yerel terminal aç")
        open_terminal.clicked.connect(self.open_local_terminal)
        empty_l.addWidget(open_terminal, 0, Qt.AlignmentFlag.AlignHCenter)
        self.pages.addWidget(self.empty)
        self.tabs = QTabWidget()
        self.tabs.setTabBar(WorkspaceTabBar(self.tabs))
        self.tabs.tabBar().animated = self.settings.value("view/animation", True, type=bool)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(lambda _: self.update_counts())
        self.pages.addWidget(self.tabs)
        self.command = QLineEdit()
        self.command.setPlaceholderText("İşaretli oturumlarda çalıştırılacak komut")
        self.command.returnPressed.connect(self.send_group_command)
        self.command_panel = QFrame()
        self.command_panel.setObjectName("CommandBar")
        command_bar = QHBoxLayout(self.command_panel)
        command_bar.setContentsMargins(8, 6, 8, 6)
        command_bar.addWidget(self.command, 1)
        send = QPushButton("Toplu gönder")
        send.clicked.connect(self.send_group_command)
        command_bar.addWidget(send)
        self.mirror_input = QCheckBox("Terminal girişini eşle")
        self.mirror_input.setToolTip(tr("İşaretli bir terminalde yazılan tuşlar ve yapıştırılan metin diğer işaretli terminallere de gönderilir."))
        command_bar.addWidget(self.mirror_input)
        stage.addWidget(self.pages, 1)
        stage.addWidget(self.command_panel)
        self.command_panel.hide()
        splitter.addWidget(workspace)
        splitter.setSizes([290, 990])
        self.status = QStatusBar(self)
        self.status.showMessage(tr("KeePass durumu kontrol ediliyor..."))
        self.setStatusBar(self.status)


    def _make_shortcuts(self):
        for shortcut, action in [("Ctrl+K", self.search.setFocus), ("Ctrl+N", self.add_server),
                                 ("Ctrl+W", self.close_current_tab), ("F5", self.refresh_sources)]:
            key = QShortcut(QKeySequence(shortcut), self)
            key.activated.connect(action)

    def run_job(self, fn, success=None, error=None):
        job = AsyncJob(fn)
        self.jobs[job.signals] = (job, success, error)
        job.signals.result.connect(self.finish_job, Qt.ConnectionType.QueuedConnection)
        self.pool.start(job)
        return job

    @Slot(object)
    def finish_job(self, result):
        _job, success, error = self.jobs.pop(self.sender())
        ok, value = result
        if ok and success:
            success(value)
        elif not ok:
            if error:
                error(value)
            else:
                self.status.showMessage(value, 12000)

    def refresh_sources(self):
        if not self.closing:
            self.refresh_hub(force=True)
            self.refresh_list(force=True)

    def toggle_hub(self, continuation=None):
        continuation = continuation if callable(continuation) else None
        if self.hub_credentials:
            self.hub_credentials = None
            self.hub_stamp = None
            self.hub_items = []
            self.hub_passwords = {}
            self.hub_btn.setText("KeePassXC kasasını aç")
            self.update_items()
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("KeePassXC · SSH Hub")
        form = QFormLayout(dialog)
        database = QLineEdit(self.settings.value("hub/database", "", type=str), dialog)
        keyfile = QLineEdit(self.settings.value("hub/keyfile", "", type=str), dialog)
        master = QLineEdit(dialog)
        master.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(tr("KDBX dosyası"), NodeForm.file_field(dialog, database, tr("KeePass kasası (*.kdbx)")))
        form.addRow(tr("Anahtar dosyası (varsa)"), NodeForm.file_field(dialog, keyfile, "Tüm dosyalar (*)"))
        form.addRow(tr("Kasa parolası"), master)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        localize(dialog)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not Path(database.text()).is_file():
            QMessageBox.warning(self, "KeePassXC", tr("Bir KDBX dosyası seçin."))
            return
        self.hub_credentials = (database.text(), master.text(), keyfile.text())
        master.clear()
        self.hub_btn.setText("KeePassXC kasasını kilitle")
        self.refresh_hub(force=True, interactive=True, continuation=continuation)

    def refresh_hub(self, force=False, interactive=False, continuation=None):
        credentials = self.hub_credentials
        if self.closing or not credentials or self.hub_loading:
            return
        try:
            info = Path(credentials[0]).stat()
            stamp = (info.st_mtime_ns, info.st_size)
        except OSError:
            stamp = None
        if not force and stamp == self.hub_stamp:
            return
        self.hub_loading = True
        self.hub_btn.setEnabled(False)

        def loaded(result):
            self.hub_loading = False
            self.hub_btn.setEnabled(True)
            self.hub_items, self.hub_passwords, skipped = result
            self.hub_stamp = stamp
            if interactive:
                self.settings.setValue("hub/database", credentials[0])
                self.settings.setValue("hub/keyfile", credentials[2])
            self.update_items()
            self.hub_btn.setToolTip(f"{len(self.hub_items)} SSH entries, {skipped} invalid entries")
            self.status.showMessage(f"SSH Hub: {len(self.hub_items)} servers · {skipped} invalid entries", 8000)
            if continuation:
                continuation()
            elif interactive and not self.hub_items:
                QMessageBox.information(self, "SSH Hub", tr("Bağlantı kaydı bulunamadı. KeePassXC'de Kullanıcı adı ve ssh://sunucu:22 biçiminde URL girin."))

        def failed(message):
            self.hub_loading = False
            self.hub_btn.setEnabled(True)
            self.toggle_hub()
            QMessageBox.warning(self, "KeePassXC", message)

        self.run_job(lambda: load_ssh_hub(*credentials), loaded, failed)

    def check_status(self):
        if self.closing or self._checking:
            return
        self._checking = True
        self.run_job(self.bridge.status, self._status_ok, self._status_error)

    def _status_ok(self, data):
        self._checking = False
        self.keepass_badge.show()
        good = bool(data.get("unlocked") and data.get("paired"))
        self.is_unlocked = bool(data.get("unlocked"))
        self.is_paired = bool(data.get("paired"))
        if good:
            self.keepass_badge.setText(tr("● KeePass 2 bağlı"))
            self.keepass_badge.setProperty("state", "ok")
            self.status.showMessage(tr("KeePass bağlantısı aktif") + (" · " + data.get("database", "") if data.get("database") else ""))
            self.refresh_list()
        elif self.is_unlocked:
            self.keepass_badge.setText(tr("KeePass 2 eşleştirmesi gerekli"))
            self.keepass_badge.setProperty("state", "warn")
            self.status.showMessage(tr("KeePass açık. NodeDeck erişimini onaylayın."))
        else:
            self.keepass_badge.setText(tr("KeePass 2 kilitli"))
            self.keepass_badge.setProperty("state", "bad")
            self.status.showMessage(tr("KeePass kilitli · açık SSH oturumları çalışmaya devam ediyor."))
        self.keepass_badge.style().unpolish(self.keepass_badge)
        self.keepass_badge.style().polish(self.keepass_badge)
        self.pair_btn.setVisible(self.is_unlocked and not self.is_paired)

        if self._last_good_state and not good:
            self.vault_unavailable()
        self._last_good_state = good
    def _status_error(self, message):
        self._checking = False
        self.is_unlocked = False
        self.is_paired = False
        self.keepass_badge.setText(tr("●  KeePass 2 çevrimdışı"))
        self.keepass_badge.hide()
        self.keepass_badge.setProperty("state", "bad")
        self.keepass_badge.style().unpolish(self.keepass_badge)
        self.keepass_badge.style().polish(self.keepass_badge)
        self.pair_btn.setVisible(False)

        if not self.status.currentMessage() or self.status.currentMessage() == tr("KeePass durumu kontrol ediliyor..."):
            self.status.showMessage(tr("Elle parola ve KeePassXC profilleri kullanılabilir."), 4000)
        if self._last_good_state:
            self.vault_unavailable()
        self._last_good_state = False

    def vault_unavailable(self):
        """KeePass erişilemezken aktif SSH bağlantılarına dokunma.

        Yalnızca yeni parola okuma, sunucu ekleme ve düzenleme geçici olarak
        engellenir. Sunucu listesi bellekte parolasız tutulur, sekmeler açık kalır.
        """
        self._last_list = 0.0  # Kilit açılınca KeePass listesini tekrar eşitle.
        self.status.showMessage(
            tr("KeePass kilitli/kapalı · mevcut SSH oturumları korunuyor. Yeni bağlantı için KeePass'i açın."),
            10000,
        )

    def on_pair(self):
        if not self.is_unlocked:
            return
        self.pair_btn.setEnabled(False)
        self.run_job(self.bridge.pair, lambda _: self._pair_done(), self._pair_error)

    def _pair_done(self):
        self.pair_btn.setEnabled(True)
        self.status.showMessage(tr("KeePass eşleştirmesi tamamlandı."), 8000)
        self.check_status()

    def _pair_error(self, text):
        self.pair_btn.setEnabled(True)
        QMessageBox.warning(self, tr("Eşleştirme başarısız"), text)

    def refresh_list(self, force=False):
        if self.closing or not self.is_unlocked or not self.is_paired or self._list_refreshing:
            return
        if not force and time.monotonic() - self._last_list < 10:
            return
        self._list_refreshing = True
        self.run_job(self.bridge.entries, self._list_ok, self._list_error)

    def _list_ok(self, items):
        self._list_refreshing = False
        if not self.is_unlocked or not self.is_paired:
            return
        self.vault_items = items
        self._last_list = time.monotonic()
        self.update_items()

    def update_items(self):
        self.items = sorted(self.local_profiles + self.vault_items + self.hub_items,
                            key=lambda n: (n.get("group", "").casefold(), n.get("name", "").casefold()))
        self.populate_tree()
        self.update_counts()

    def _list_error(self, message):
        self._list_refreshing = False
        self.status.showMessage(tr("Kayıtlar okunamadı: ") + message, 12000)

    def populate_tree(self):
        needle = self.search.text().strip().casefold()
        selected = self.selected_server()
        selected_id = selected.get("id") if selected else None
        expanded = {path: node.isExpanded() for path, node in self.groups.items()}
        self.tree.clear()
        groups = {}

        def ensure_folder(path):
            parent = self.tree.invisibleRootItem()
            parts = []
            for segment in path.split("/"):
                parts.append(segment)
                key = "/".join(parts)
                if key not in groups:
                    node = QTreeWidgetItem(parent, [segment])
                    node.setData(0, Qt.ItemDataRole.UserRole + 1, key)
                    node.setFlags(node.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
                    node.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                    groups[key] = node
                parent = groups[key]
            return parent

        if not needle:
            for path in self.folder_paths:
                ensure_folder(path)
        for entry in self.items:
            group_name = self.display_folder(entry)
            haystack = " ".join([group_name, *(str(entry.get(k, "")) for k in ("name", "host", "username"))])
            if needle and needle not in haystack.casefold():
                continue
            parent = ensure_folder(group_name) if group_name else self.tree.invisibleRootItem()
            child = QTreeWidgetItem([entry["name"], entry["host"]])
            child.setData(0, Qt.ItemDataRole.UserRole, entry["id"])
            child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsDropEnabled)
            source = {"manual": "Elle parola", "xc": "KeePassXC", "hub": "SSH Hub"}.get(entry.get("source"), "KeePass 2")
            child.setToolTip(0, f'{entry["username"]}@{entry["host"]}:{entry["port"]} · {source}')
            parent.addChild(child)
            if entry["id"] == selected_id:
                self.tree.setCurrentItem(child)
        for path, node in groups.items():
            node.setExpanded(bool(needle) or expanded.get(path, True))
        self.tree.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.groups = groups
        self.empty_servers.setVisible(not self.items)
        self.device_count.setText(tr("{count} sunucu").format(count=len(self.items)))

    def selected_server(self):
        selection = self.tree.currentItem()
        if not selection:
            return None
        entry_id = selection.data(0, Qt.ItemDataRole.UserRole)
        return next((e for e in self.items if e.get("id") == entry_id), None)

    def tree_double_click(self, item, _column):
        if item.data(0, Qt.ItemDataRole.UserRole):
            self.connect_server(self.selected_server())

    def display_folder(self, entry):
        return self.locations[entry["id"]] if entry["id"] in self.locations else entry.get("group", "")

    def save_folder_layout(self, paths, locations):
        if self.folder_error:
            QMessageBox.warning(self, tr("Klasörler"), tr("Klasör ayarları okunamadı. Mevcut dosya korunuyor."))
            return
        try:
            folders.save(paths, locations)
        except OSError:
            QMessageBox.warning(self, tr("Klasörler"), tr("Klasör düzeni kaydedilemedi."))
            return
        self.folder_paths, self.locations = paths, locations
        self.populate_tree()

    def create_selected_folder(self):
        node = self.tree.currentItem()
        parent = node.data(0, Qt.ItemDataRole.UserRole + 1) if node else ""
        self.create_folder(parent or "")

    def create_folder(self, parent=""):
        name, accepted = QInputDialog.getText(self, tr("Yeni klasör"), tr("Klasör adı"))
        name = name.strip()
        if not accepted:
            return
        if not name or "/" in name or name in (".", ".."):
            QMessageBox.warning(self, tr("Klasörler"), tr("Geçerli bir klasör adı girin. Ad / içeremez."))
            return
        path = f"{parent}/{name}" if parent else name
        if path not in self.groups and path not in self.folder_paths:
            self.save_folder_layout([*self.folder_paths, path], dict(self.locations))

    def move_profile(self, entry):
        paths = set(self.folder_paths) | {self.display_folder(profile) for profile in self.items}
        paths.update({path for path in self.locations.values()})
        all_paths = {"/".join(parts[:length]) for parts in map(lambda path: path.split("/"), paths)
                     for length in range(1, len(parts) + 1)}
        options = ["Use original folder", "No folder", *sorted(all_paths - {""}, key=str.casefold)]
        target, accepted = QInputDialog.getItem(self, tr("Sunucuyu taşı"), tr("Hedef klasör"), options, 0, False)
        if not accepted:
            return
        self.place_profile(entry["id"], None if target == options[0] else "" if target == options[1] else target)

    def place_profile(self, entry_id, target):
        if not any(entry["id"] == entry_id for entry in self.items):
            return
        locations = dict(self.locations)
        if target is not None:
            locations[entry_id] = target
        else:
            locations.pop(entry_id, None)
        self.save_folder_layout(list(self.folder_paths), locations)

    def rename_folder(self, path):
        parent, _, original = path.rpartition("/")
        name, accepted = QInputDialog.getText(self, tr("Klasörü yeniden adlandır"), tr("Klasör adı"), text=original)
        name = name.strip()
        if not accepted or name == original:
            return
        target = f"{parent}/{name}" if parent else name
        if not name or "/" in name or name in (".", "..") or target in self.groups or target in self.folder_paths:
            QMessageBox.warning(self, tr("Klasörler"), tr("Farklı ve geçerli bir klasör adı girin."))
            return

        def move(value):
            return target + value[len(path):] if value == path or value.startswith(path + "/") else value

        paths = sorted({move(value) for value in [*self.folder_paths, path]})
        locations = {key: move(value) for key, value in self.locations.items()}
        for entry in self.items:
            old = self.display_folder(entry)
            if move(old) != old:
                locations[entry["id"]] = move(old)
        self.save_folder_layout(paths, locations)

    def remove_folder(self, path):
        if any(self.display_folder(entry) == path or self.display_folder(entry).startswith(path + "/")
               for entry in self.items) or any(value == path or value.startswith(path + "/")
                                                for value in self.locations.values()):
            QMessageBox.information(self, tr("Klasörler"), tr("Önce klasördeki sunucuları başka bir klasöre taşıyın."))
            return
        self.save_folder_layout([value for value in self.folder_paths
                                 if value != path and not value.startswith(path + "/")], dict(self.locations))

    def tree_menu(self, pos):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        if item is None:
            menu.addAction(tr("Yeni klasör"), lambda: self.create_folder())
            localize(menu)
            menu.exec(self.tree.viewport().mapToGlobal(pos))
            return
        self.tree.setCurrentItem(item)
        entry = self.selected_server()
        if entry is None:
            path = item.data(0, Qt.ItemDataRole.UserRole + 1)
            menu.addAction("Bu klasöre sunucu ekle", lambda: self.add_server(path))
            menu.addAction("Alt klasör ekle", lambda: self.create_folder(path))
            menu.addAction(tr("Yeniden adlandır"), lambda: self.rename_folder(path))
            menu.addAction("Boş klasörü sil", lambda: self.remove_folder(path))
            localize(menu)
            menu.exec(self.tree.viewport().mapToGlobal(pos))
            return
        menu.addAction("SSH bağlantısı aç", lambda: self.connect_server(entry))
        menu.addAction("SFTP aç", lambda: self.open_server_sftp(entry))
        menu.addAction("Klasöre taşı", lambda: self.move_profile(entry))
        if entry.get("source") != "hub":
            menu.addAction("Kaydı düzenle", lambda: self.edit_server(entry))
        if entry.get("source") in ("manual", "xc"):
            menu.addAction(tr("Profili sil"), lambda: self.delete_profile(entry))
        menu.addSeparator()
        copy = menu.addMenu("Copy")
        for label, value in (("Username", entry["username"]), ("Host", entry["host"]),
                             ("Port", entry["port"]), ("SSH URL", self.ssh_url(entry)),
                             ("Folder path", self.display_folder(entry))):
            copy.addAction(label, lambda checked=False, text=value: QApplication.clipboard().setText(text))
        if entry.get("source") != "manual" or entry.get("protected_password"):
            copy.addAction("Password", lambda: self.copy_server_password(entry))
        localize(menu)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def ssh_url(self, entry):
        from urllib.parse import quote
        host = entry["host"]
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f'ssh://{quote(entry["username"], safe="")}@{host}:{entry["port"]}'

    def copy_server_password(self, entry):
        def copy(password):
            if not password or self.closing:
                return
            clipboard = QApplication.clipboard()
            clipboard.setText(password)
            marker = sha256(password.encode("utf-8")).digest()
            self.clipboard_password = marker
            QTimer.singleShot(self.settings.value("security/clipboard", 30, type=int) * 1000,
                              lambda: self.clear_copied_password(marker))
            self.status.showMessage("Password copied temporarily.", 4000)

        source = entry.get("source")
        if source == "manual":
            def unlocked():
                current = next((item for item in self.local_profiles if item["id"] == entry["id"]), None)
                if current and current.get("protected_password"):
                    try:
                        copy(self.password_vault.decrypt(current["id"], current["protected_password"]))
                    except ValueError as error:
                        QMessageBox.warning(self, "Local vault", str(error))
            self.unlock_local_vault(unlocked)
        elif source == "hub":
            copy(self.hub_passwords.get(entry["id"]))
        elif source == "xc":
            self.connect_with_xc(entry, on_password=copy)
        elif self.is_unlocked and self.is_paired:
            self.run_job(lambda: self.bridge.password(entry["id"]), copy)
        else:
            self.status.showMessage("Unlock the KeePass vault first.", 5000)

    def clear_copied_password(self, marker):
        if marker is not None and marker == self.clipboard_password:
            clipboard = QApplication.clipboard()
            if sha256(clipboard.text().encode("utf-8")).digest() == marker:
                clipboard.clear()
            self.clipboard_password = None

    def add_server(self, folder=None):
        if not isinstance(folder, str):
            item = self.tree.currentItem()
            folder = item.data(0, Qt.ItemDataRole.UserRole + 1) if item else None
            if not folder and self.selected_server():
                folder = self.display_folder(self.selected_server())
        sources = {"Yerel profil": "manual", "KeePassXC": "hub"}
        if self.is_unlocked and self.is_paired:
            sources["KeePass 2"] = "keepass"
        label, accepted = QInputDialog.getItem(self, tr("Yeni sunucu"), tr("Parola kaynağı"), [tr(name) for name in sources], 0, False)
        if accepted:
            self.edit_server(source=next(value for name, value in sources.items() if tr(name) == label), default_group=folder or "")

    def edit_server(self, entry=None, source="keepass", default_group=""):
        if entry:
            source = entry.get("source", "keepass")
        if source == "keepass" and not (self.is_unlocked and self.is_paired):
            self.status.showMessage(tr("Önce KeePass 2 kasasını açıp eşleştirin."), 5000)
            return
        if source == "hub" and not self.hub_credentials:
            self.toggle_hub(lambda: self.edit_server(entry, source, default_group))
            return
        dialog = NodeForm(self, item=entry, existing_groups=set(self.groups) | set(self.folder_paths), source=source, default_group=default_group)
        localize(dialog)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.save_server(dialog.values())

    def change_local_profiles(self, entry_id, replacement=None):
        if self.vault_busy:
            self.status.showMessage("Wait for the local vault to finish opening.", 5000)
            return
        try:
            profiles = [entry for entry in load_profiles() if entry["id"] != entry_id]
            if replacement is not None:
                profiles.append(replacement)
            save_profiles(profiles)
        except (OSError, ValueError):
            QMessageBox.warning(self, tr("Yerel profiller"), tr("Profil dosyası okunamadı veya kaydedilemedi."))
            return
        self.local_profiles = profiles
        self.update_items()

    def delete_profile(self, entry):
        if QMessageBox.question(self, tr("Profili sil"), tr("Delete profile {name}?").format(name=entry["name"])) == QMessageBox.StandardButton.Yes:
            self.change_local_profiles(entry["id"])

    def toggle_local_vault(self):
        if self.password_vault.unlocked:
            self.password_vault.lock()
            self.clear_copied_password(self.clipboard_password)
            self.local_vault_btn.setText("Unlock local vault")
        else:
            self.unlock_local_vault()

    def unlock_local_vault(self, continuation=None):
        if self.password_vault.unlocked:
            if continuation:
                continuation()
            return
        if self.vault_busy:
            self.status.showMessage("The local vault is opening.", 5000)
            return
        create = not self.password_vault.exists
        if create and any((profile.get("protected_password") or "").startswith(PREFIX)
                          for profile in self.local_profiles):
            QMessageBox.warning(self, "Local vault", "The vault header is missing. Restore password-vault.json to unlock saved passwords.")
            return
        title = "Create local vault" if create else "Unlock local vault"
        prompt = "Choose a master password (at least 12 characters)" if create else "Master password"
        master, accepted = QInputDialog.getText(self, title, prompt, QLineEdit.EchoMode.Password)
        if not accepted:
            return
        if create:
            confirmation, accepted = QInputDialog.getText(self, title, "Confirm master password", QLineEdit.EchoMode.Password)
            if not accepted:
                return
            if master != confirmation:
                QMessageBox.warning(self, title, "Passwords do not match.")
                return
        self.vault_busy = True
        self.local_vault_btn.setEnabled(False)

        def unlock():
            self.password_vault.unlock(master, create=create)
            try:
                profiles = load_profiles()
                migrated = migrate_profiles(profiles, self.password_vault, unprotect)
                if profiles != migrated:
                    save_profiles(migrated)
                return migrated
            except Exception:
                self.password_vault.lock()
                raise ValueError("The saved profiles could not be migrated. The existing profiles were kept.") from None

        def ready(profiles):
            self.vault_busy = False
            self.local_vault_btn.setEnabled(True)
            if self.closing:
                self.password_vault.lock()
                return
            self.local_vault_btn.setText("Lock local vault")
            self.local_profiles = profiles
            self.update_items()
            if continuation:
                continuation()

        def failed(message):
            self.vault_busy = False
            self.local_vault_btn.setEnabled(True)
            if not self.closing:
                QMessageBox.warning(self, title, message)

        self.run_job(unlock, ready, failed)

    def save_server(self, entry):
        if entry["source"] == "hub":
            credentials = self.hub_credentials
            if credentials and not self.hub_loading:
                answer = QMessageBox.question(self, "Save to KeePassXC",
                    "Close this vault in KeePassXC before saving here, then reopen it to see the new record. Continue?")
                if answer == QMessageBox.StandardButton.Yes:
                    self.hub_loading = True
                    self.hub_btn.setEnabled(False)

                    def finished(error=None):
                        self.hub_loading = False
                        self.hub_btn.setEnabled(True)
                        if error:
                            QMessageBox.warning(self, "KeePassXC", error)
                        else:
                            self.refresh_hub(force=True)

                    self.run_job(lambda: save_ssh_hub_entry(credentials, entry),
                                 lambda _: finished(), finished)
            return
        if entry["source"] in ("manual", "xc"):
            entry["id"] = entry["id"] or "local:" + uuid4().hex
            password = entry.get("password", "")
            if (entry["source"] == "manual" and entry.get("auth") not in ("key", "agent")
                    and password and (self.vault_busy or not self.password_vault.unlocked)):
                self.unlock_local_vault(lambda: self.save_server(entry))
                return
            entry.pop("password", None)
            if entry["source"] == "manual":
                previous = next((profile.get("protected_password", "") for profile in self.local_profiles
                                 if profile["id"] == entry["id"]), "")
                try:
                    if entry.get("auth") in ("key", "agent") or (not password and entry["forget_password"]):
                        entry["protected_password"] = ""
                    elif password:
                        entry["protected_password"] = self.password_vault.encrypt(entry["id"], password)
                    else:
                        entry["protected_password"] = previous
                except Exception:
                    QMessageBox.warning(self, tr("Parola"), "Could not encrypt the password. The profile was not saved.")
                    return
            self.change_local_profiles(entry["id"], entry)
            return
        entry = {field: entry[field] for field in ("id", "name", "host", "port", "username", "password", "group")}
        self.status.showMessage(tr("Kayıt KeePass'e yazılıyor..."))
        self.run_job(lambda: self.bridge.save(entry),
                     lambda _: self._save_done(),
                     lambda msg: QMessageBox.critical(self, tr("Kayıt kaydedilemedi"), msg))

    def _save_done(self):
        self._last_list = 0.0
        self.status.showMessage(tr("SSH kaydı KeePass'e kaydedildi."), 6000)
        self.refresh_list(force=True)

    def open_server_sftp(self, entry):
        pane = next((pane for pane in self.session_views
                     if pane.entry.get("id") == entry["id"] and pane.connected), None)
        if pane:
            self.open_sftp(pane)
        else:
            self.connect_server(entry, sftp=True)

    def connect_server(self, entry, sftp=False):
        if not entry:
            return
        source = entry.get("source")
        if source == "hub":
            if self.hub_loading:
                self.status.showMessage(tr("KeePassXC kayıtları yenileniyor."), 4000)
                return
            password = self.hub_passwords.get(entry["id"])
            if password:
                self._start_ssh(entry, password, sftp)
            else:
                QMessageBox.warning(self, "KeePassXC", tr("SSH Hub kaydında parola yok veya kasa kilitli."))
            return
        if source == "manual":
            if entry.get("auth") == "key":
                keyfile = entry.get("ssh_key", "")
                if not keyfile or not Path(keyfile).is_file():
                    QMessageBox.warning(self, "SSH", tr("SSH özel anahtar dosyası bulunamadı."))
                    return
                passphrase, accepted = QInputDialog.getText(self, "OpenSSH", tr("Anahtar parolası (varsa)"), QLineEdit.EchoMode.Password)
                if accepted:
                    self._start_ssh(entry, None, sftp, keyfile=keyfile, passphrase=passphrase or None)
                return
            if entry.get("auth") == "agent":
                self._start_ssh(entry, None, sftp, agent=True)
                return
            if entry.get("protected_password"):
                self.unlock_local_vault(lambda: self.connect_saved_password(entry["id"], sftp))
                return
            password, accepted = QInputDialog.getText(self, tr("SSH parolası"),
                tr("SSH parolası") + f' · {entry["username"]}@{entry["host"]}', QLineEdit.EchoMode.Password)
            if accepted:
                self._start_ssh(entry, password, sftp)
            return
        if source == "xc":
            self.connect_with_xc(entry, sftp)
            return
        if not (self.is_unlocked and self.is_paired):
            QMessageBox.information(
                self,
                tr("KeePass kilidini açın"),
                "Unlock the KeePass vault to start a new SSH session. Existing sessions remain connected.",
            )
            return
        self.status.showMessage(entry["name"] + tr(" parolası KeePass'ten alınıyor..."))
        self.run_job(lambda: self.bridge.password(entry["id"]),
                     lambda password, e=dict(entry): self._start_ssh(e, password, sftp),
                     lambda msg: QMessageBox.warning(self, tr("SSH bağlantısı"), msg))

    def connect_saved_password(self, identifier, sftp):
        entry = next((profile for profile in self.local_profiles if profile["id"] == identifier), None)
        if not entry or not entry.get("protected_password"):
            return
        try:
            password = self.password_vault.decrypt(identifier, entry["protected_password"])
        except ValueError as error:
            QMessageBox.warning(self, tr("Parola"), str(error))
            return
        self._start_ssh(entry, password, sftp)

    def connect_with_xc(self, entry, sftp=False, on_password=None):
        cli = find_cli()
        if not cli:
            cli, _ = QFileDialog.getOpenFileName(self, tr("keepassxc-cli.exe dosyasını seçin"), "", "KeePassXC CLI (keepassxc-cli.exe)")
        if not cli:
            return
        prompt = tr("KDBX kasasının ana parolası")
        if entry["key_file"]:
            prompt += tr(" (yalnızca anahtar dosyası kullanılıyorsa boş bırakın)")
        master, accepted = QInputDialog.getText(self, "KeePassXC", prompt, QLineEdit.EchoMode.Password)
        if not accepted:
            return
        self.run_job(
            lambda: read_password(cli, entry["database"], entry["xc_entry"], master, entry["key_file"]),
            on_password or (lambda password: self._start_ssh(entry, password, sftp)),
            lambda message: QMessageBox.warning(self, "KeePassXC", message),
        )

    def apply_layout(self):
        self.pages.setCurrentWidget(self.tabs if self.tabs.count() else self.empty)

    def choose_split(self):
        if len(self.session_views) < 2:
            self.status.showMessage(tr("Bölmek için en az iki oturum açın."), 5000)
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Oturumları böl…"))
        layout = QVBoxLayout(dialog)
        direction = QComboBox(dialog)
        direction.addItem(tr("Yan yana"), Qt.Orientation.Horizontal)
        direction.addItem(tr("Alt alta"), Qt.Orientation.Vertical)
        direction.setCurrentIndex(int(self.settings.value("view/split", "horizontal") == "vertical"))
        layout.addWidget(direction)
        choices = []
        current = self.tabs.currentWidget()
        for index, pane in enumerate(self.session_views, 1):
            box = QCheckBox(f'{index}. {pane.entry["name"]} · {pane.entry["host"]}', dialog)
            box.setChecked(pane is current or pane.parent() is current)
            choices.append((box, pane))
            layout.addWidget(box)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            panes = [pane for box, pane in choices if box.isChecked() and pane in self.session_views]
            if len(panes) >= 2:
                self.group_sessions(panes, direction.currentData())
            else:
                self.status.showMessage(tr("En az iki oturum seçin."), 5000)

    def group_sessions(self, panes, orientation):
        group = QSplitter(orientation)
        group.setChildrenCollapsible(False)
        group.setHandleWidth(4)
        for pane in panes:
            index = self.tabs.indexOf(pane)
            if index >= 0:
                self.tabs.removeTab(index)
            group.addWidget(pane)
            pane.show()
        self.split_groups.append(group)
        self.clean_split_groups()
        self.tabs.addTab(group, " / ".join(pane.entry["name"] for pane in panes))
        self.tabs.setCurrentWidget(group)
        self.apply_layout()

    def clean_split_groups(self):
        for group in list(self.split_groups):
            if group.count() >= 2:
                self.tabs.setTabText(self.tabs.indexOf(group), " / ".join(
                    group.widget(i).entry["name"] for i in range(group.count())))
                continue
            index = self.tabs.indexOf(group)
            if index >= 0:
                self.tabs.removeTab(index)
            if group.count():
                pane = group.widget(0)
                self.tabs.addTab(pane, pane.entry["name"])
            self.split_groups.remove(group)
            group.deleteLater()

    def separate_current(self):
        group = self.tabs.currentWidget()
        if group not in self.split_groups:
            return
        while group.count():
            pane = group.widget(0)
            self.tabs.addTab(pane, pane.entry["name"])
        self.clean_split_groups()
        self.apply_layout()

    def route_terminal_input(self, source, data):
        if not source.connected or source not in self.panes:
            return
        self.panes[source][1].send(data)
        if self.mirror_input.isChecked() and source.broadcast_target.isChecked():
            for pane, (_thread, worker) in self.panes.items():
                if pane is not source and pane.connected and pane.broadcast_target.isChecked():
                    worker.send(data)

    def send_group_command(self):
        command = self.command.text().strip()
        if not command:
            return
        targets = [(pane, self.panes[pane][1]) for pane in self.session_views
                   if pane.connected and pane.broadcast_target.isChecked() and pane in self.panes]
        if not targets:
            self.status.showMessage(tr("Toplu komut için bağlı oturumları işaretleyin."), 6000)
            return
        names = "\n".join(f'{pane.entry["name"]} · {pane.entry["host"]}' for pane, _ in targets)
        answer = QMessageBox.question(self, tr("Toplu SSH komutu"),
            tr("Komut, aşağıdaki oturumların mevcut terminal girdisine gönderilecek.") + f"\n\n{command}\n\n{names}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        payload = (command + "\r").encode("utf-8")
        for pane, worker in targets:
            if pane.connected and pane in self.panes:
                worker.send(payload)
        self.command.clear()

    def export_local(self):
        if self.vault_busy:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export local backup", "NodeDeck-backup.zip", "ZIP (*.zip)")
        if path:
            try:
                if any(item.get("protected_password") and not item["protected_password"].startswith(PREFIX)
                       for item in self.local_profiles):
                    raise ValueError("Unlock the local vault to migrate legacy passwords before exporting.")
                export_backup(path)
                self.status.showMessage("Local backup exported.", 5000)
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, "Export local backup", str(error))

    def import_local(self):
        if self.vault_busy:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Import local backup", "", "ZIP (*.zip)")
        if not path:
            return
        try:
            backup = read_backup(path)
            if QMessageBox.question(self, "Import local backup",
                "Replace current local profiles, folders and password vault with this backup?") != QMessageBox.StandardButton.Yes:
                return
            restore_backup(backup)
            self.password_vault.lock()
            self.clear_copied_password(self.clipboard_password)
            self.local_vault_btn.setText("Unlock local vault")
            self.local_profiles = load_profiles()
            self.folder_paths, self.locations = folders.load()
            self.folder_error = False
            self.update_items()
        except Exception as error:
            QMessageBox.warning(self, "Import local backup", str(error))

    def check_updates(self, silent=False, url_override=None):
        if self.closing or self.update_busy:
            return
        url = (url_override if url_override is not None else self.settings.value("updates/url", DEFAULT_FEED_URL, type=str)).strip()
        if not url:
            if not silent:
                self.status.showMessage("Save an HTTPS release manifest URL in Settings first.", 8000)
            return
        self.update_busy = True

        def done(result=None, error=None):
            self.update_busy = False
            if self.closing:
                return
            if result:
                version, download = result
                if QMessageBox.question(self, "Update available",
                    f"Version {version} is available. Open the installer download page?") == QMessageBox.StandardButton.Yes:
                    QDesktopServices.openUrl(QUrl(download))
            elif not silent:
                self.status.showMessage(error or "NodeDeck SSH is up to date.", 8000)

        self.run_job(lambda: check_release(url), done, lambda error: done(error=error))

    def open_preferences(self):
        dialog = Preferences(self, self.settings)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            apply_preferences(self.settings)
            self.tabs.tabBar().animated = self.settings.value("view/animation", True, type=bool)
            for pane in self.session_views:
                pane.terminal.configure(self.settings)
            localize(self)
            self.update_counts()

    def open_sftp(self, pane):
        if not pane.connected or pane not in self.panes:
            return
        worker = self.panes[pane][1]
        transport = worker.client.get_transport() if worker.client else None
        if transport is None or not transport.is_active():
            self.status.showMessage(tr("SFTP için SSH oturumu açık olmalı."), 6000)
            return
        if self.settings.value("view/sftp", True, type=bool):
            if pane.sftp_panel is None:
                pane.sftp_panel = SftpDialog(pane, pane.entry["name"], transport, self.run_job)
                pane.sftp_panel.setWindowFlags(Qt.WindowType.Widget)
                pane.content.addWidget(pane.sftp_panel)
                width = self.settings.value("view/sftp_ratio", 42, type=int)
                pane.content.setSizes([100 - width, width])
                pane.sftp_panel.show()
                localize(pane.sftp_panel)
                pane.sftp_panel.browse(".")
            else:
                pane.sftp_panel.setVisible(pane.sftp_panel.isHidden())
            return
        dialog = SftpDialog(self, pane.entry["name"], transport, self.run_job)
        localize(dialog)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()
        dialog.browse(".")

    def _start_ssh(self, entry, password, sftp=False, *, keyfile=None, passphrase=None, agent=False):
        if self.closing:
            return
        if entry.get("source") not in ("manual", "xc", "hub") and not (self.is_unlocked and self.is_paired):
            return
        pane = SessionPane(entry)
        pane.close_requested.connect(lambda p=pane: self.close_pane(p))
        pane.sftp_requested.connect(lambda p=pane: self.open_sftp(p))
        pane.reconnect.clicked.connect(lambda: self.reconnect_pane(pane))
        pane.terminal.configure(self.settings)
        localize(pane)
        self.session_views.append(pane)
        self.tabs.addTab(pane, pane.entry["name"])
        self.tabs.setCurrentWidget(pane)
        self.apply_layout()
        worker = SSHSession(entry["host"], entry["port"], entry["username"], password, keyfile=keyfile, passphrase=passphrase, agent=agent, keepalive=self.settings.value("ssh/keepalive", 20, type=int))
        thread = QThread(self)
        worker.moveToThread(thread)
        worker.output.connect(pane.terminal.feed)
        worker.connected.connect(pane.set_connected)
        pane.open_sftp_on_connect = sftp
        pane.ready_for_sftp.connect(lambda p=pane: self.open_sftp(p))
        worker.disconnected.connect(pane.set_disconnected)
        worker.hostkey.connect(lambda host, kind, fp, w=worker: self._verify_key(w, host, kind, fp))
        pane.terminal.input_bytes.connect(lambda data, p=pane: self.route_terminal_input(p, data))
        pane.terminal.resized_grid.connect(worker.resize, Qt.ConnectionType.DirectConnection)
        worker.resize(*pane.terminal.grid_size())
        thread.started.connect(worker.run)
        worker.disconnected.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda p=pane, t=thread: self._thread_finished(p, t))
        thread.finished.connect(thread.deleteLater)
        self.panes[pane] = (thread, worker)
        thread.start()
        self.update_counts()

    def reconnect_pane(self, pane):
        entry = next((item for item in self.items if item["id"] == pane.entry.get("id")), pane.entry)
        self.connect_server(entry)

    def open_local_terminal(self):
        if os.name != "nt":
            QMessageBox.information(self, tr("Yerel terminal"), tr("Yerel CMD terminali Windows'ta kullanılabilir."))
            return
        pane = SessionPane(dict(name=tr("Yerel CMD"), username="", host=tr("Bu bilgisayar"), port=""))
        pane.broadcast_target.hide()
        pane.sftp_button.hide()
        pane.close_requested.connect(lambda p=pane: self.close_pane(p))
        pane.terminal.configure(self.settings)
        localize(pane)
        self.session_views.append(pane)
        self.tabs.addTab(pane, pane.entry["name"])
        self.tabs.setCurrentWidget(pane)
        self.apply_layout()
        worker = LocalTerminal(*pane.terminal.grid_size())
        thread = QThread(self)
        worker.moveToThread(thread)
        worker.output.connect(pane.terminal.feed)
        worker.connected.connect(pane.set_connected)
        worker.disconnected.connect(pane.set_disconnected)
        pane.terminal.input_bytes.connect(worker.send, Qt.ConnectionType.DirectConnection)
        pane.terminal.resized_grid.connect(worker.resize, Qt.ConnectionType.DirectConnection)
        thread.started.connect(worker.run)
        worker.disconnected.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda p=pane, t=thread: self._thread_finished(p, t))
        thread.finished.connect(thread.deleteLater)
        self.panes[pane] = (thread, worker)
        thread.start()
        self.update_counts()

    def _thread_finished(self, pane, thread):
        current = self.panes.get(pane)
        if current and current[0] is thread:
            self.panes.pop(pane, None)
        self.update_counts()

    def _verify_key(self, worker, host, keytype, fingerprint):
        answer = QMessageBox.question(
            self, tr("Yeni SSH sunucu anahtarı"),
            tr("Bu sunucuya ilk kez bağlanıyorsunuz:") + f"\n\n{host}\n{keytype}\n{fingerprint}\n\n"
            + tr("Bağlanmadan önce parmak izini doğrulayın. Bu anahtara güvenip known_hosts dosyasına kaydetmek istiyor musunuz?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        worker.approve_key(answer == QMessageBox.StandardButton.Yes)

    def close_pane(self, pane):
        entry = self.panes.get(pane)
        if entry:
            _thread, worker = entry
            try:
                worker.stop()
            except RuntimeError:
                pass
        index = self.tabs.indexOf(pane)
        if index >= 0:
            self.tabs.removeTab(index)
        if pane in self.session_views:
            self.session_views.remove(pane)
        pane.setParent(None)
        pane.deleteLater()
        self.clean_split_groups()
        self.apply_layout()
        self.update_counts()

    def close_tab(self, idx):
        pane = self.tabs.widget(idx)
        if pane in self.split_groups:
            for child in [pane.widget(i) for i in range(pane.count())]:
                self.close_pane(child)
        elif pane:
            self.close_pane(pane)

    def close_current_tab(self):
        if self.tabs.currentIndex() >= 0 and self.pages.currentWidget() is self.tabs:
            self.close_tab(self.tabs.currentIndex())

    def update_counts(self):
        total = len(self.panes)
        self.hint.setText(tr("{count} açık oturum").format(count=total) if total else "")
        mode = self.settings.value("view/multi", "always", type=str)
        self.command_panel.setVisible(mode == "always" or
                                      (mode == "split" and self.tabs.currentWidget() in self.split_groups))

    def closeEvent(self, event):
        self.closing = True
        self.clear_copied_password(self.clipboard_password)
        self.poll.stop()
        if not self.vault_busy:
            self.password_vault.lock()
        for _pane, (_thread, worker) in list(self.panes.items()):
            worker.stop()
        if self.panes or self.jobs:
            event.ignore()
            QTimer.singleShot(100, self.close)
            return
        event.accept()


def launch():
    smoke_test = "--smoke-test" in sys.argv
    if smoke_test and getattr(sys, "frozen", False) and os.name == "nt":
        if not (BASE / "python3.dll").is_file():
            raise RuntimeError("Packaged python3.dll is missing.")
    app = QApplication(sys.argv)
    app.setApplicationName("NodeDeck SSH")
    app.setOrganizationName("NodeDeck")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI" if os.name == "nt" else "Sans Serif", 10))
    palette = app.palette()
    for role, color in {
        "Window": "#232429", "WindowText": "#e2e2e5", "Base": "#1b1c20",
        "AlternateBase": "#25262a", "Text": "#e2e2e5", "Button": "#303137",
        "ButtonText": "#e2e2e5", "Highlight": "#594333", "HighlightedText": "#fff0dc",
        "PlaceholderText": "#a8aab3", "Light": "#4a4b52", "Dark": "#18191c",
    }.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(color))
    app.setPalette(palette)
    if STYLE_FILE.exists():
        app.setStyleSheet(STYLE_FILE.read_text(encoding="utf-8").replace("@ASSETS@", STYLE_FILE.parent.as_posix()))
    if ICON_FILE.exists():
        app.setWindowIcon(QIcon(str(ICON_FILE)))
    apply_preferences(QSettings("NodeDeck", "NodeDeck SSH"))
    window = MainWindow()
    window.show()
    if smoke_test:
        QTimer.singleShot(200, window.close)
    return app.exec()


if __name__ == "__main__":
    sys.exit(launch())
