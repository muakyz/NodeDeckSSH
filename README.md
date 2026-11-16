# NodeDeck SSH v0.10.2

Windows 10/11 için sekmeli SSH bağlantı yöneticisi. Yeni sunucu eklerken parola kaynağını seçebilirsiniz.

## Build and publish on GitHub

### One-time setup

1. Create a public GitHub repository and put the **contents** of the `NodeDeckSSH` directory at its root. Include `.github/workflows/release.yml` and `.gitignore`. Public release assets are downloadable without a GitHub login. The repository should contain only source and packaging files.
2. In **Settings → Pages**, select **GitHub Actions** as the publishing source. Set the custom domain to `updates.waytfeys.uk`. At your DNS provider, create a **CNAME** from `updates` to `GITHUB-OWNER.github.io` using your actual account or organization name. For Cloudflare DNS, use **DNS only** for the Pages CNAME. Leave the root domain as configured. Enable **Enforce HTTPS** once GitHub provisions the certificate.
3. If the `github-pages` environment restricts deployments to particular branches, allow the release tags used by this workflow under **Settings → Environments → github-pages → Deployment branches and tags**. Allow tags matching `v*`.
4. In the desktop application's **Settings → Data & updates**, existing installations with a custom feed can change it to `https://updates.waytfeys.uk/latest.json`. Version 0.10.2 uses this address by default.

### Publish each release

The first included release version is `0.10.2`. For later versions, change `VERSION` in `release_updates.py` and `AppVersion` in `NodeDeckInstaller.iss` to the same number and push your commit. Create a matching Git tag from the commit you want to release:

```sh
git tag v0.10.2
git push origin v0.10.2
```

**Actions → Windows release** builds the Windows Setup EXE, publishes it under **Releases**, and deploys `latest.json` to GitHub Pages. The domain serves the update manifest. GitHub Releases serves `NodeDeckSSH-Setup.exe`. The update checker opens the installer download link after confirmation. For local builds, run `build_installer.bat` on Windows with Python 3.11–3.13 x64 and Inno Setup 6. The target PC does not need Python.

The workflow currently produces unsigned builds. A code-signing service can be integrated later to sign the application before packaging and the installer before publication.

## Local profiles and backups

- Leave **Folder** blank to place a server at the root of the list. The empty server list offers an **Add a server** shortcut. **Move to folder → No folder** also moves an existing server to the root.
- **New server** offers local storage and KeePassXC. KeePass 2 is available when its bridge is unlocked and paired. KeePassXC entries are written under `SSH Hub`. Close the selected database in KeePassXC before writing from NodeDeckSSH, then reopen it to see the changes.
- The server context menu has **Copy** options for username, host, port, SSH URL, folder path and saved password. Passwords require the applicable vault to be unlocked. The application clears an unchanged password from the clipboard after the configured timeout.
- **Settings → Data & updates** displays your local data path, normally `%LOCALAPPDATA%/NodeDeckSSH`. `profiles.json` holds local profiles and encrypted SSH passwords, `password-vault.json` holds the vault header, and `folders.json` holds the folder layout.
- **Export backup** packages these files in a ZIP. **Import backup** replaces those three local files after confirmation. Open restored passwords with the original vault master password. KeePass databases and private SSH key files are separate files.
- SFTP shows transfer percentages for uploads and downloads. **Settings** lets you set panel width and choose whether the MultiExec bar is always visible, shown in split tabs only, or hidden.

## Workspace and settings

- Every connection opens in its own tab. **Split sessions…** combines the selected sessions in a resizable horizontal or vertical tab. **Separate tabs** restores the individual tabs.
- Right-click a folder and choose **Add server here**. Drag existing profiles onto another folder or use **Move to folder**.
- A local profile can use a password, an OpenSSH private key, or an SSH agent. Private key passphrases are entered at connection time.
- **SFTP** opens beside the terminal by default. It supports file uploads, multiple file uploads, local file drop, downloads, folder creation and rename. The separate SFTP window is available through Settings.
- **Settings** stores the language, theme, split direction, terminal font and size, cursor blink, tab animation, SFTP placement and SSH keepalive. English is the default. Turkish, German and French are available. Some secondary messages fall back to English in German and French.

## Terminal imleci ve pano

- Bağlı terminalde imleç görünür. Odaktaki terminalin imleci yanıp söner, bağlantı kapanınca gizlenir.
- Seçili metni **Ctrl+C** ile kopyalayın. Seçim yoksa **Ctrl+C** kesme sinyali gönderir. **Ctrl+V** ile yapıştırın. Sağ tık menüsünde de kopyalama ve yapıştırma bulunur.
- Bölücüleri sürükleyerek sunucu listesini ve terminalleri boyutlandırın. Yan yana ve alt alta görünümlerin boyutları uygulama açıkken ayrı ayrı korunur.

## Terminaller ve SFTP

- Birden fazla SSH oturumu açın. **Split sessions…** ile istediğiniz oturumları aynı sekmede yan yana veya alt alta açın. Bölücüyü sürükleyerek terminal boyutlarını değiştirebilirsiniz.
- Hedef terminallerde **Toplu komuta dahil et** kutusunu işaretleyin. Alt alana bir komut yazıp **Toplu gönder** ile seçilen bağlı terminallere gönderin. **Terminal girişini eşle** seçeneğini açarsanız işaretli bir terminaldeki tuşlar ve yapıştırılan metin diğer işaretli terminallere de gider. Bu seçenek başlangıçta kapalıdır.
- Bağlı terminalde **SFTP** düğmesini açın. Klasörleri çift tıklayarak gezin. **Dosya yükle** yerel dosyayı uzak klasöre gönderir. **Dosya indir** seçili uzak dosyayı kaydeder. Uzak sunucuda SFTP alt sistemi etkin olmalıdır.
- Sunucular sol listede grup başlıkları altında görünür. Elle eklenen profilde **Grup** alanını seçebilir veya yeni bir ad yazabilirsiniz. KeePassXC profillerinin grubu kasadaki SSH Hub klasör yapısından gelir.

## Sunucu listesi ve yerel terminal

- Sol listede **+ Klasör** ile klasör oluşturun. Klasöre sağ tıklayarak alt klasör ekleyebilir veya yeniden adlandırabilirsiniz. Sunucuya sağ tıklayıp **Klasöre taşı** ile listede yerini değiştirin. Klasör düzeni bu bilgisayarda saklanır. KeePass kayıtları kendi kasasında kalır.
- Arama kutusu sunucu adı, IP, kullanıcı ve klasör adını arar.
- Sunucuya sağ tıklayıp **SFTP aç** seçeneğini kullanın. Bağlantı yoksa uygulama normal SSH kimlik doğrulamasıyla bağlanır ve dosya penceresini açar.
- **+ Terminal** ile sunucu seçmeden yerel Windows CMD açın. Buradan `ssh kullanıcı@adres` gibi komutları çalıştırabilirsiniz. Yerel terminal, sekme ve bölünmüş görünümde kullanılabilir.

## EXE oluşturma

1. Python 3.11–3.13 x64 ve internet erişimi olan bir Windows bilgisayarda ZIP'i çıkarın.
2. `build_windows.bat` dosyasını çalıştırın. İşlem sonunda `dist/NodeDeckSSH.exe` oluşur.
3. EXE'yi hedef Windows'a kopyalayın. Hedefte Python gerekmez. İsteğe bağlı kurulum paketi için derleme bilgisayarında Inno Setup kullanılabilir.

## KeePassXC ile SSH Hub

1. KeePassXC'de kasanın kökünde **SSH Hub** grubu oluşturun. Alt gruplar açabilirsiniz.
2. Her sunucu için bir kayıt ekleyin. **Başlık** sunucunun görünen adı, **Kullanıcı adı** SSH hesabı, **Parola** SSH parolası, **URL** ise örneğin `ssh://192.168.1.50:22` olmalı. URL'de port yazılmazsa 22 kullanılır.
3. KeePassXC'de kasayı kaydedin. NodeDeckSSH'de **KeePassXC kasasını aç** düğmesine tıklayın. KDBX dosyanızı ve varsa anahtar dosyanızı seçip kasa parolasını girin.
4. SSH Hub ve alt gruplarındaki geçerli kayıtlar sunucu listesine gelir. Bir sunucuya çift tıklayıp bağlanın. KeePassXC'de kaydettiğiniz değişiklikler birkaç saniye içinde listelenir. **Yenile** ile elle de güncelleyebilirsiniz.

NodeDeckSSH KDBX dosyasını listeleme sırasında salt okunur açar. Yeni sunucuda KeePassXC seçildiğinde seçili kasaya kayıt yazabilir. KeePassXC penceresinin kilit durumu ile NodeDeckSSH'nin kasa oturumu bağımsızdır. Ana parola ve SSH parolaları yalnızca NodeDeckSSH kasa oturumu boyunca bellekte tutulur. **KeePassXC kasasını kilitle** ile kasa oturumunu kapatabilirsiniz. Açık SSH bağlantıları çalışmaya devam eder. Donanım anahtarıyla kasa açma desteklenmez. Eski v0.9.2 KeePassXC profilleri çalışmaya devam eder ve eski akışta CLI kullanır.

## KeePass olmadan kullanım

1. **Yeni sunucu → Elle parola** seçin.
2. Sunucu adresini, portu ve kullanıcı adını yazın. Parolayı saklamak için **Parola** alanını doldurup **Profili kaydet** düğmesine basın. Alanı boş bırakırsanız parola bağlantı sırasında sorulur.
3. İlk kayıtta en az 12 karakterli bir ana parola ile yerel kasa oluşturun. **Lock local vault** ile kilitleyebilirsiniz. Açık bağlantılar çalışmaya devam eder.
4. Eski DPAPI parolaları ilk kasa açılışında aynı Windows hesabında yeni biçime taşınır. Bir kayıt çözülemezse mevcut profil dosyası korunur. Gerekirse o profilde kayıtlı parolayı silip tekrar girin.

Yerel kasa anahtarını Argon2id ile türetir ve SSH parolalarını libsodium SecretBox (XSalsa20-Poly1305) ile korur. Profil bilgileri ve şifreli parolalar `%LOCALAPPDATA%/NodeDeckSSH/profiles.json` içinde, kasa başlığı `password-vault.json` içinde bulunur. Taşımak için iki dosyayı birlikte kopyalayın. Ana parolayı kaybederseniz kayıtlı SSH parolaları kurtarılamaz.

## KeePass Password Safe 2.x ile kullanım

1. Hedef Windows'ta ZIP'teki `install_bridge.bat` betiğini çalıştırın. Program Files klasörüne yazmak için yönetici yetkisi gerekebilir. Portable KeePass kullanıyorsanız istendiğinde `KeePass.exe` yolunu girin.
2. KeePass'i tamamen kapatıp açın. **Tools → Plugins** içinde **NodeDeckBridge** eklentisini kontrol edin.
3. Kasayı açın, NodeDeckSSH'yi başlatın ve **KeePass ile eşleştir** düğmesinden erişimi onaylayın.
4. `SSH Hub` grubundaki veya başlığı `[SSH]` ile başlayan kayıtları kullanın. KeePass kaydındaki URL alanında `ssh://sunucu:22` biçimini kullanın. **Yeni sunucu → KeePass 2** ile kasaya yeni kayıt eklenebilir.

KeePass 2 kilitlendiğinde yeni KeePass 2 bağlantısı için kasayı açın. Açık SSH oturumları çalışmaya devam eder.

## Güvenlik notları

1. **KeePass kilidi açıldığında kayıtlardaki parola, SSH kimlik doğrulaması sırasında kısa süreliğine uygulama belleğine alınır; bu kaçınılmazdır.** Uygulama parolaları log'a/dosyaya yazmaz. Bağlantı kurulunca oturum nesnesindeki parola referansı temizlenir.
2. Pipe yalnızca aynı Windows kullanıcı SID'ine izin verir. İlk eşleştirme KeePass içinde bir diyalogla onaylanır. Sonraki eşleştirmede DPAPI belirteci kullanılır. Aynı Windows kullanıcısı altında çalışan kötü niyetli yazılımlara karşı tam koruma sağlanamaz.
3. Eklenti KeePass içinde tam erişimle çalışır. Kodu inceleyip güvenerek yükleyin. KeePass > Tools > **NodeDeck: Eşleştirmeyi İptal Et** ile erişimi iptal edebilirsiniz.
4. SSH anahtarını ilk bağlantıda sunucunun kendi konsolundan doğrulayın. Değişen tanınmış SSH host key hiçbir şekilde otomatik kabul edilmez.
5. Sürüm 0.9: **parola ile SSH** ve temel xterm/ANSI ekran işleme mevcut. Bazı tam ekran konsol uygulamaları (`vim`, `htop`, `nano`), ANSI renkler ve fare olayları tam terminal emülatörü kalitesinde olmayabilir. OpenSSH özel anahtar ve SSH agent ile giriş desteklenir. RDP henüz yok.
6. KeePass 2 erişimi uygulama tarafından yaklaşık **3 saniyede bir** kontrol edilir. Bu kontrol yalnızca KeePass'ten yeni parola/kayıt alınmasını etkiler; halihazırda doğrulanmış SSH oturumları KeePass'ten bağımsızdır ve KeePass kilitlense veya kapansa bile açık kalır. Kasa parolaları diske yazılmaz. Elle kaydedilen SSH parolaları yerel kasa ana parolasıyla korunur.
7. Bu prototip Windows ortamında KeePass 2 ile entegrasyon testi yapılamadan paketlendi. İlk kullanımda deneme KDBX veritabanıyla test etmeniz ve mevcut KDBX'in yedeğini almanız önerilir.

## Proje dosyaları

| Dosya | İşlev |
| --- | --- |
| `main.py` | PySide6 Windows GUI |
| `ssh_engine.py` | SSH bağlantısı, host anahtarı kontrolü |
| `terminal_view.py` | Temel terminal gösterimi ve klavye |
| `bridge_client.py` | Windows named pipe KeePass istemcisi |
| `keepass-bridge/NodeDeckBridge.cs` | KeePass 2 eklentisi kaynak kodu |
| `install_bridge.bat` / `.ps1` | DLL derleme/kurma |
| `build_windows.bat` | Tek EXE derleme |
| `NodeDeckInstaller.iss` | İsteğe bağlı kurulum EXE'si |
| `assets/style.qss` | Windows arayüz teması |

---

**Not:** KeePass normal kullanıcının yönetici yetkisiyle çalışıp NodeDeck'in normal kullanıcı olarak çalışması halinde Windows oturum/yetki sınırları farklılaşabilir. İkisini aynı oturum/ağırlıkta çalıştırın. Eklentinin kullandığı veritabanı KeePass'te *aktif* olan sekmedir.
