"""Persistent workspace preferences."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QSpinBox, QTabWidget, QVBoxLayout, QWidget, QPushButton, QLineEdit, QLabel,
)

language = "en"

# Labels shared by the main workspace and its dialogs.
LABELS = {
    "Ayarlar": ("Settings", "Einstellungen", "Paramètres"),
    "Sunucular": ("Servers", "Server", "Serveurs"),
    "+ Klasör": ("+ Folder", "+ Ordner", "+ Dossier"),
    "+ Terminal": ("+ Terminal", "+ Terminal", "+ Terminal"),
    "+  Yeni sunucu": ("+ New server", "+ Neuer Server", "+ Nouveau serveur"),
    "Yenile": ("Refresh", "Aktualisieren", "Actualiser"),
    "KeePassXC kasasını aç": ("Open KeePassXC vault", "KeePassXC-Tresor öffnen", "Ouvrir le coffre KeePassXC"),
    "KeePassXC kasasını kilitle": ("Lock KeePassXC vault", "KeePassXC-Tresor sperren", "Verrouiller le coffre KeePassXC"),
    "Açık oturum yok": ("No open sessions", "Keine offenen Sitzungen", "Aucune session ouverte"),
    "Bağlanmak için listeden bir sunucuya çift tıkla.": ("Double-click a server to connect.", "Zum Verbinden auf einen Server doppelklicken.", "Double-cliquez sur un serveur pour vous connecter."),
    "Yerel terminal aç": ("Open local terminal", "Lokales Terminal öffnen", "Ouvrir un terminal local"),
    "Sekmeler": ("Tabs", "Registerkarten", "Onglets"),
    "Yan yana": ("Side by side", "Nebeneinander", "Côte à côte"),
    "Alt alta": ("Stacked", "Untereinander", "Superposés"),
    "Oturumları böl…": ("Split sessions…", "Sitzungen teilen…", "Scinder les sessions…"),
    "Sekmelere ayır": ("Separate tabs", "Registerkarten trennen", "Séparer les onglets"),
    "Toplu gönder": ("Send to selected", "An Auswahl senden", "Envoyer à la sélection"),
    "Terminal girişini eşle": ("Mirror input", "Eingabe spiegeln", "Répliquer la saisie"),
    "Toplu": ("Group", "Gruppe", "Groupe"),
    "Bağlanıyor…": ("Connecting…", "Verbindung…", "Connexion…"),
    "● Bağlı": ("● Connected", "● Verbunden", "● Connecté"),
    "Kapalı": ("Closed", "Geschlossen", "Fermé"),
    "Kapat": ("Close", "Schließen", "Fermer"),
    "Sunucu": ("Server", "Server", "Serveur"),
    "Adres": ("Address", "Adresse", "Adresse"),
    "Dosya yükle": ("Upload", "Hochladen", "Téléverser"),
    "Dosya indir": ("Download", "Herunterladen", "Télécharger"),
    "Üst klasör": ("Parent folder", "Übergeordneter Ordner", "Dossier parent"),
    "Git": ("Go", "Öffnen", "Aller"),
    "Ad": ("Name", "Name", "Nom"),
    "Tür": ("Type", "Typ", "Type"),
    "Boyut (bayt)": ("Size (bytes)", "Größe (Bytes)", "Taille (octets)"),
    "Yeni klasör": ("New folder", "Neuer Ordner", "Nouveau dossier"),
    "Yeniden adlandır": ("Rename", "Umbenennen", "Renommer"),
    "Klasöre taşı": ("Move to folder", "In Ordner verschieben", "Déplacer vers un dossier"),
    "Bu klasöre sunucu ekle": ("Add server here", "Server hier hinzufügen", "Ajouter un serveur ici"),
    "Alt klasör ekle": ("Add subfolder", "Unterordner hinzufügen", "Ajouter un sous-dossier"),
    "Boş klasörü sil": ("Delete empty folder", "Leeren Ordner löschen", "Supprimer le dossier vide"),
    "SSH bağlantısı aç": ("Connect via SSH", "Per SSH verbinden", "Connexion SSH"),
    "SFTP aç": ("Open SFTP", "SFTP öffnen", "Ouvrir SFTP"),
    "Kaydı düzenle": ("Edit profile", "Profil bearbeiten", "Modifier le profil"),
    "Profili sil": ("Delete profile", "Profil löschen", "Supprimer le profil"),
    "Sunucu adresini kopyala": ("Copy server address", "Serveradresse kopieren", "Copier l’adresse"),
    "Bağlantı adı": ("Profile name", "Profilname", "Nom du profil"),
    "Sunucu / IP": ("Host / IP", "Host / IP", "Hôte / IP"),
    "Kullanıcı": ("Username", "Benutzername", "Utilisateur"),
    "Parola": ("Password", "Passwort", "Mot de passe"),
    "Grup": ("Folder", "Ordner", "Dossier"),
    "Kimlik doğrulama": ("Authentication", "Authentifizierung", "Authentification"),
    "OpenSSH anahtarı": ("OpenSSH key", "OpenSSH-Schlüssel", "Clé OpenSSH"),
    "SSH özel anahtar dosyası": ("SSH private key file", "Private SSH-Schlüsseldatei", "Fichier de clé SSH privée"),
    "Gözat…": ("Browse…", "Durchsuchen…", "Parcourir…"),
    "Profili kaydet": ("Save profile", "Profil speichern", "Enregistrer le profil"),
    "Vazgeç": ("Cancel", "Abbrechen", "Annuler"),
    "Yeni SSH bağlantısı": ("New SSH connection", "Neue SSH-Verbindung", "Nouvelle connexion SSH"),
    "Sunucuyu düzenle": ("Edit server", "Server bearbeiten", "Modifier le serveur"),
    "Sunucu ara...  Ctrl+K": ("Search servers…  Ctrl+K", "Server suchen…  Ctrl+K", "Rechercher…  Ctrl+K"),
    "İşaretli oturumlarda çalıştırılacak komut": ("Command for selected sessions", "Befehl für ausgewählte Sitzungen", "Commande pour les sessions sélectionnées"),
    "Dil": ("Language", "Sprache", "Langue"),
    "Tema": ("Theme", "Design", "Thème"),
    "Bölme yönü": ("Split direction", "Teilungsrichtung", "Direction du partage"),
    "Terminal yazı tipi": ("Terminal font", "Terminalschrift", "Police du terminal"),
    "Terminal yazı boyutu": ("Terminal font size", "Schriftgröße", "Taille du texte"),
    "Yanıp sönen imleç": ("Blinking cursor", "Blinkender Cursor", "Curseur clignotant"),
    "SFTP yan paneli": ("SFTP side panel", "SFTP-Seitenleiste", "Panneau latéral SFTP"),
    "Sekme animasyonu": ("Tab animation", "Registeranimation", "Animation des onglets"),
    "Kopyala": ("Copy", "Kopieren", "Copier"),
    "Yapıştır": ("Paste", "Einfügen", "Coller"),
    "Tümünü seç": ("Select all", "Alles auswählen", "Tout sélectionner"),
}


ENGLISH = {
    'Yerel CMD': 'Local CMD',
    'Bu bilgisayar': 'This computer',
    'Yerel profil': 'Local profile',
    'Yeniden bağlan': 'Reconnect',
    'Bölmek için en az iki oturum açın.': 'Open at least two sessions to split the workspace.',
    'En az iki oturum seçin.': 'Select at least two sessions.',
    'Yeni sunucu': 'New server',
    'Parola kaynağı': 'Credential source',
    'Klasör adı': 'Folder name',
    'Klasörler': 'Folders',
    'Hedef klasör': 'Destination folder',
    'Sunucuyu taşı': 'Move server',
    'Klasörü yeniden adlandır': 'Rename folder',
    '(Kaydın kendi grubuna dön)': '(Use original folder)',
    'Klasör düzeni kaydedilemedi.': 'Could not save the folder layout.',
    'Klasör ayarları okunamadı. Mevcut dosya korunuyor.': 'Could not read folder settings. The existing file was preserved.',
    'Geçerli bir klasör adı girin. Ad / içeremez.': 'Enter a folder name without slashes.',
    'Farklı ve geçerli bir klasör adı girin.': 'Enter a different valid folder name.',
    'Önce klasördeki sunucuları başka bir klasöre taşıyın.': 'Move the servers out of this folder first.',
    'Kasa parolası': 'Vault password',
    'KDBX dosyası': 'KDBX file',
    'Anahtar dosyası (varsa)': 'Key file (optional)',
    'Bir KDBX dosyası seçin.': 'Select a KDBX file.',
    'Anahtar parolası (varsa)': 'Key passphrase (optional)',
    'SSH parolası': 'SSH password',
    'Kayıtlı parolayı sil': 'Remove saved password',
    "KeePass'e kaydet": 'Save to KeePass',
    'KeePass ile eşleştir': 'Pair with KeePass',
    'SSH parolası her bağlantıda sorulur.': 'Save a password or enter it when connecting.',
    'SSH parolası seçilen KeePassXC kaydından alınır.': 'Read the SSH password from the selected KeePassXC entry.',
    'Bağlantı bilgileri doğrudan KeePass veritabanına kaydedilir.': 'Save the connection details to the KeePass vault.',
    'İsteğe bağlı · boşsa bağlantıda sorulur': 'Optional · leave blank to enter it when connecting',
    'Kayıtlı parolayı korumak için boş bırakın': 'Leave blank to keep the saved password',
    'Geçerli bir SSH özel anahtar dosyası seçin.': 'Select a valid SSH private key file.',
    'SSH özel anahtar dosyası bulunamadı.': 'SSH private key file not found.',
    'Dosya seç': 'Select file',
    'Tüm dosyalar (*)': 'All files (*)',
    'Klasör': 'Folder',
    'Dosya': 'File',
    '{count} öğe': '{count} items',
    'İşlem başarısız.': 'Operation failed.',
    'Klasör okunuyor…': 'Reading directory…',
    'Klasör oluşturuluyor…': 'Creating folder…',
    'Yeniden adlandırılıyor…': 'Renaming…',
    'Dosya yükleniyor…': 'Uploading…',
    'Dosya indiriliyor…': 'Downloading…',
    'Dosya indirildi.': 'Download complete.',
    'Dosyayı kaydet': 'Save file',
    'Yüklenecek dosyalar': 'Select files to upload',
    'İndirmek için bir dosya seçin.': 'Select a file to download.',
    'Dosya işlemi tamamlandıktan sonra pencereyi kapatabilirsiniz.': 'Wait for the transfer to finish before closing this window.',
    'SSH oturumu kapalı.': 'SSH session closed.',
    'Bu isimde bir uzak dosya zaten var.': 'A remote file with this name already exists.',
    'SSH Hub kaydında parola yok veya kasa kilitli.': 'The SSH Hub entry has no password or the vault is locked.',
    'Toplu komut için bağlı oturumları işaretleyin.': 'Select connected sessions to send a group command.',
    'SFTP için SSH oturumu açık olmalı.': 'An active SSH session is required for SFTP.',
    '{count} sunucu': '{count} servers',
    '{count} açık oturum': '{count} open sessions',
    'Bu oturumu toplu komuta dahil et': 'Include this session in group commands',
    'İşaretli bir terminalde yazılan tuşlar ve yapıştırılan metin diğer işaretli terminallere de gönderilir.': 'Send keystrokes and pasted text to all selected terminals.',
}


LABELS.update({
    'Yeniden bağlan': ('Reconnect', 'Erneut verbinden', 'Reconnecter'),
    'Yeni sunucu': ('New server', 'Neuer Server', 'Nouveau serveur'),
    'Yerel profil': ('Local profile', 'Lokales Profil', 'Profil local'),
    'Parola kaynağı': ('Credential source', 'Quelle der Zugangsdaten', 'Source des identifiants'),
    'Hedef klasör': ('Destination folder', 'Zielordner', 'Dossier de destination'),
    'Klasör adı': ('Folder name', 'Ordnername', 'Nom du dossier'),
    'Kasa parolası': ('Vault password', 'Tresorpasswort', 'Mot de passe du coffre'),
    'SSH parolası': ('SSH password', 'SSH-Passwort', 'Mot de passe SSH'),
    'Dosya yükleniyor…': ('Uploading…', 'Wird hochgeladen…', 'Téléversement…'),
    'Dosya indiriliyor…': ('Downloading…', 'Wird heruntergeladen…', 'Téléchargement…'),
    'Klasör okunuyor…': ('Reading directory…', 'Ordner wird gelesen…', 'Lecture du dossier…'),
    'Klasör': ('Folder', 'Ordner', 'Dossier'),
    'Dosya': ('File', 'Datei', 'Fichier'),
    '{count} sunucu': ('{count} servers', '{count} Server', '{count} serveurs'),
    '{count} açık oturum': ('{count} open sessions', '{count} offene Sitzungen', '{count} sessions ouvertes'),
})

ENGLISH.update({
    'Genel': 'General',
    'Ağ Cihazları': 'Network devices',
    'Yerel profiller': 'Local profiles',
    'Kayıt yolu': 'Entry path',
    'Bir sunucuyu çift tıklayarak bağlan': 'Double-click a server to connect',
    'KeePass durumu kontrol ediliyor...': 'Checking KeePass status…',
    'KDBX kasasının ana parolası': 'KDBX vault password',
    ' (yalnızca anahtar dosyası kullanılıyorsa boş bırakın)': ' (leave empty for a key-file-only vault)',
    "Yerel CMD terminali Windows'ta kullanılabilir.": 'Local CMD is available on Windows.',
    'KeePassXC kayıtları yenileniyor.': 'Refreshing KeePassXC entries.',
    'SSH bağlantısı': 'SSH connection',
    'Toplu SSH komutu': 'Group SSH command',
    'Yeni SSH sunucu anahtarı': 'New SSH host key',
    'Kimlik doğrulama başarısız. Kullanıcı ve kimlik doğrulama ayarlarını kontrol edin.': 'Authentication failed. Check the username and authentication settings.',
    'GÜVENLİK: Sunucunun SSH anahtarı değişmiş! Bağlantı engellendi.': 'The server host key has changed. The connection was blocked.',
    'Oturum kapatıldı': 'Session closed',
    'Yerel terminal kapandı.': 'Local terminal closed.',
    'Sunucu anahtarı kullanıcı tarafından onaylanmadı.': 'The server host key was declined.',
    'Kasanın kökünde SSH Hub grubu bulunamadı.': 'SSH Hub was not found at the root of the vault.',
    'Kasa açılamadı. Ana parolayı ve varsa anahtar dosyasını kontrol edin.': 'Could not unlock the vault. Check its password and key file.',
    'KDBX dosyası okunamadı. Dosya yolunu ve kasa biçimini kontrol edin.': 'Could not read the KDBX file. Check the path and vault format.',
    'Ad, IP, kullanıcı ve grup alanları zorunludur.': 'Name, host, username and folder are required.',
    'IP / sunucu adında boşluk olamaz.': 'The host name or IP cannot contain spaces.',
    'Profil dosyası okunamadı veya kaydedilemedi.': 'Could not read or save the profile file.',
    'Windows parolayı şifreleyemedi. Profil kaydedilmedi.': 'Windows could not encrypt the password. The profile was not saved.',
    'Kayıtlı parola bu Windows hesabında açılamadı. Parolayı yeniden girin.': 'This Windows account could not decrypt the saved password. Enter the password again.',
    "Bağlantı kaydı bulunamadı. KeePassXC'de Kullanıcı adı ve ssh://sunucu:22 biçiminde URL girin.": 'No connections found. In KeePassXC, enter a username and a URL like ssh://host:22.',
    'KeePass kilidini açın': 'Unlock KeePass',
    'Önce KeePass 2 kasasını açıp eşleştirin.': 'Unlock and pair the KeePass 2 vault first.',
    '● KeePass 2 bağlı': '● KeePass 2 connected',
    'KeePass 2 eşleştirmesi gerekli': 'KeePass 2 pairing required',
    'KeePass 2 kilitli': 'KeePass 2 locked',
    'Elle parola ve KeePassXC profilleri kullanılabilir.': 'Local and KeePassXC profiles are available.',
})

ENGLISH.update({
    "Komut, aşağıdaki oturumların mevcut terminal girdisine gönderilecek.": "Send this command to the selected terminal sessions?",
    "Bu sunucuya ilk kez bağlanıyorsunuz:": "First connection to this server:",
    "Bağlanmadan önce parmak izini doğrulayın. Bu anahtara güvenip known_hosts dosyasına kaydetmek istiyor musunuz?": "Verify the fingerprint before connecting. Trust this key and save it to known_hosts?",
})


ENGLISH.update({
    'Yerel profil dosyası okunamadı.': 'Could not read the local profile file.',
    'Profil dosyası okunamadı. Dosya düzeltilene kadar yerel kayıtlar değiştirilemez.': 'The local profile file could not be read. Repair it before editing profiles.',
    "Bağlantı kaydı bulunamadı. KeePassXC'de Kullanıcı adı ve ssh://sunucu:22 biçiminde URL girin.": 'No server records found. Add a server here or enter a username and an ssh://host:22 URL in KeePassXC.',
    'KeePass bağlantısı aktif': 'KeePass connection active',
    'KeePass açık. NodeDeck erişimini onaylayın.': 'KeePass is open. Approve NodeDeck access.',
    'KeePass kilitli · açık SSH oturumları çalışmaya devam ediyor.': 'KeePass is locked. Open SSH sessions remain connected.',
    "KeePass kilitli/kapalı · mevcut SSH oturumları korunuyor. Yeni bağlantı için KeePass'i açın.": 'Unlock KeePass for new connections. Existing SSH sessions remain connected.',
    'KeePass eşleştirmesi tamamlandı.': 'KeePass pairing complete.',
    'Eşleştirme başarısız': 'Pairing failed',
    'Kayıtlar okunamadı: ': 'Could not read records: ',
    "Kayıt KeePass'e yazılıyor...": 'Saving to KeePass…',
    'Kayıt kaydedilemedi': 'Could not save profile',
    "SSH kaydı KeePass'e kaydedildi.": 'SSH profile saved to KeePass.',
    " parolası KeePass'ten alınıyor...": ' · retrieving password from KeePass…',
    'keepassxc-cli.exe dosyasını seçin': 'Select keepassxc-cli.exe',
    'Yerel terminal': 'Local terminal',
    '●  KeePass 2 çevrimdışı': '● KeePass 2 offline',
    'Örn. Proxmox / WEB-01': 'e.g. Proxmox / WEB-01',
    'Değiştirmemek için boş bırakın': 'Leave blank to keep the current password',
    'KeePass içinde şifreli saklanır': 'Stored in the KeePass vault',
    'KeePass kasası (*.kdbx)': 'KeePass vault (*.kdbx)',
    'Mevcut bir KDBX dosyası ve kayıt yolu girin.': 'Select an existing KDBX file and enter the entry path.',
    'Anahtar dosyası bulunamadı.': 'Key file not found.',
})

def tr(text):
    entry = LABELS.get(text)
    if language == "tr":
        return text
    if entry:
        return entry[("en", "de", "fr").index(language)]
    return ENGLISH.get(text, text)


def localize(root):
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QAbstractButton, QLabel, QLineEdit, QTreeWidget
    for widget in [root, *root.findChildren(QLabel), *root.findChildren(QAbstractButton),
                   *root.findChildren(QLineEdit), *root.findChildren(QComboBox),
                   *root.findChildren(QTreeWidget), *root.findChildren(QAction)]:
        if isinstance(widget, (QLabel, QAbstractButton, QAction)):
            original = widget.property("original_text")
            if original is None:
                original = widget.text()
                widget.setProperty("original_text", original)
            widget.setText(tr(original))
        if isinstance(widget, QLineEdit):
            original = widget.property("original_placeholder")
            if original is None:
                original = widget.placeholderText()
                widget.setProperty("original_placeholder", original)
            widget.setPlaceholderText(tr(original))
        if isinstance(widget, QComboBox) and not widget.isEditable():
            for index in range(widget.count()):
                role = 300
                original = widget.itemData(index, role)
                if original is None:
                    original = widget.itemText(index)
                    widget.setItemData(index, original, role)
                widget.setItemText(index, tr(original))
        if isinstance(widget, QTreeWidget):
            header = widget.headerItem()
            for column in range(widget.columnCount()):
                original = header.data(column, 300)
                if original is None:
                    original = header.text(column)
                    header.setData(column, 300, original)
                header.setText(column, tr(original))
    if isinstance(root, QDialog):
        root.setWindowTitle(tr(root.windowTitle()))


def apply_preferences(settings):
    global language
    language = settings.value("view/language", "en", type=str)
    if language not in ("en", "tr", "de", "fr"):
        language = "en"
    app = QApplication.instance()
    style_file = Path(__file__).resolve().parent / "assets" / "style.qss"
    stylesheet = style_file.read_text(encoding="utf-8").replace("@ASSETS@", style_file.parent.as_posix())
    if settings.value("view/theme", "graphite", type=str) == "midnight":
        for source, target in {
            "#232429": "#191f2b", "#25262a": "#1d2431", "#151619": "#101621",
            "#1b1c1f": "#151b26", "#e7b479": "#91b8f8", "#594333": "#2c476b",
        }.items():
            stylesheet = stylesheet.replace(source, target)
    app.setStyleSheet(stylesheet)


class Preferences(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(tr("Ayarlar"))
        self.setMinimumWidth(500)
        outer = QVBoxLayout(self)
        tabs = QTabWidget()
        outer.addWidget(tabs)

        def page(title):
            widget = QWidget()
            tabs.addTab(widget, title)
            return QFormLayout(widget)

        layout = page("Appearance")
        self.fields = {}

        def choices(label, key, options, default):
            field = QComboBox()
            for title, value in options:
                field.addItem(tr(title), value)
            field.setCurrentIndex(max(0, field.findData(settings.value(key, default))))
            layout.addRow(tr(label), field)
            self.fields[key] = field.currentData

        choices("Dil", "view/language", [("English", "en"), ("Türkçe", "tr"),
                ("Deutsch", "de"), ("Français", "fr")], "en")
        choices("Tema", "view/theme", [("Graphite", "graphite"), ("Midnight", "midnight")], "graphite")
        choices("Bölme yönü", "view/split", [("Yan yana", "horizontal"), ("Alt alta", "vertical")], "horizontal")
        choices("MultiExec bar", "view/multi", [("Always show", "always"),
                ("Only in split tabs", "split"), ("Hide", "hidden")], "always")
        layout = page("Terminal & SFTP")
        choices("Terminal yazı tipi", "terminal/font", [(name, name) for name in
                ("Consolas", "Cascadia Mono", "Courier New", "Monospace")], "Consolas")

        for label, key, low, high, default in (
            ("Terminal yazı boyutu", "terminal/size", 8, 28, 10),
            ("SSH keepalive (s)", "ssh/keepalive", 0, 300, 20),
            ("SFTP panel width (%)", "view/sftp_ratio", 20, 70, 42),
        ):
            field = QSpinBox()
            field.setRange(low, high)
            field.setValue(settings.value(key, default, type=int))
            layout.addRow(tr(label), field)
            self.fields[key] = field.value

        for label, key in (
            ("Yanıp sönen imleç", "terminal/blink"),
            ("SFTP yan paneli", "view/sftp"),
            ("Sekme animasyonu", "view/animation"),
        ):
            field = QCheckBox()
            field.setChecked(settings.value(key, True, type=bool))
            layout.addRow(tr(label), field)
            self.fields[key] = field.isChecked

        layout = page("Data & updates")
        from bridge_client import APP_DATA
        from release_updates import DEFAULT_FEED_URL, VERSION
        path = QLabel(str(APP_DATA))
        path.setWordWrap(True)
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addRow("Local data folder", path)
        for title, action in (("Export backup…", parent.export_local), ("Import backup…", parent.import_local)):
            button = QPushButton(title)
            button.clicked.connect(action)
            layout.addRow(button)
        clipboard = QSpinBox()
        clipboard.setRange(5, 300)
        clipboard.setValue(settings.value("security/clipboard", 30, type=int))
        layout.addRow("Clear copied password after (s)", clipboard)
        self.fields["security/clipboard"] = clipboard.value
        feed = QLineEdit(settings.value("updates/url", DEFAULT_FEED_URL, type=str))
        feed.setPlaceholderText("https://updates.waytfeys.uk/latest.json")
        layout.addRow("HTTPS release manifest", feed)
        self.fields["updates/url"] = feed.text
        automatic = QCheckBox()
        automatic.setChecked(settings.value("updates/startup", True, type=bool))
        layout.addRow("Check at startup", automatic)
        self.fields["updates/startup"] = automatic.isChecked
        check = QPushButton("Check for updates")
        check.clicked.connect(lambda: parent.check_updates(url_override=feed.text()))
        layout.addRow(f"Installed version {VERSION}", check)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def accept(self):
        for key, value in self.fields.items():
            self.settings.setValue(key, value())
        self.settings.sync()
        super().accept()
