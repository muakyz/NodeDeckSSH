// NodeDeck KeePass 2.x plugin — local-only, named-pipe protocol.
// Works with the currently ACTIVE and UNLOCKED KeePass database.
using System;
using System.IO;
using System.IO.Pipes;
using System.Collections.Generic;
using System.Security.AccessControl;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using System.Web.Script.Serialization;
using KeePass.Plugins;
using KeePassLib;
using KeePassLib.Security;

namespace NodeDeckBridge
{
    public sealed class NodeDeckBridgeExt : Plugin
    {
        private const string PipeName = "NodeDeckKeePassBridge.v1";
        private const string ConfigName = "NodeDeckBridge.AuthHash.v1";
        private IPluginHost host;
        private Thread serverThread;
        private volatile bool running;
        private ToolStripMenuItem revokeMenu;
        private readonly JavaScriptSerializer json = new JavaScriptSerializer();

        public override bool Initialize(IPluginHost h)
        {
            if (h == null) return false;
            host = h;
            try {
                revokeMenu = new ToolStripMenuItem("NodeDeck: Eşleştirmeyi İptal Et");
                revokeMenu.Click += delegate(object s, EventArgs e) {
                    if (MessageBox.Show(host.MainWindow, "NodeDeck erişimi iptal edilsin mi?", "NodeDeck", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes) {
                        host.CustomConfig.SetString(ConfigName, "");
                        MessageBox.Show(host.MainWindow, "Eşleştirme iptal edildi. Tekrar izin vermeniz gerekir.", "NodeDeck");
                    }
                };
                host.MainWindow.ToolsMenu.DropDownItems.Add(revokeMenu);
            } catch { /* menu optional; IPC still works */ }
            running = true;
            serverThread = new Thread(ServerLoop);
            serverThread.IsBackground = true;
            serverThread.Name = "NodeDeckKeePassBridge";
            serverThread.Start();
            return true;
        }

        public override void Terminate()
        {
            running = false;
            try { using (NamedPipeClientStream c = new NamedPipeClientStream(".", PipeName, PipeDirection.InOut)) c.Connect(200); } catch { }
            try { if (serverThread != null) serverThread.Join(1200); } catch { }
            try { if (revokeMenu != null) { host.MainWindow.ToolsMenu.DropDownItems.Remove(revokeMenu); revokeMenu.Dispose(); } } catch { }
        }

        private void ServerLoop()
        {
            while (running)
            {
                try {
                    PipeSecurity security = new PipeSecurity();
                    SecurityIdentifier sid = WindowsIdentity.GetCurrent().User;
                    security.SetOwner(sid);
                    security.SetAccessRule(new PipeAccessRule(sid, PipeAccessRights.ReadWrite | PipeAccessRights.CreateNewInstance, AccessControlType.Allow));
                    using (NamedPipeServerStream pipe = new NamedPipeServerStream(PipeName, PipeDirection.InOut, 1,
                        PipeTransmissionMode.Byte, PipeOptions.None, 65536, 65536, security)) {
                        pipe.WaitForConnection();
                        if (!running) break;
                        using (StreamReader reader = new StreamReader(pipe, new UTF8Encoding(false), false, 4096, true))
                        using (StreamWriter writer = new StreamWriter(pipe, new UTF8Encoding(false), 4096, true)) {
                            writer.AutoFlush = true;
                            string raw = reader.ReadLine();
                            if (raw == null || raw.Length > 65536) continue;
                            Dictionary<string, object> req = json.Deserialize<Dictionary<string, object>>(raw);
                            object response = host.MainWindow.Invoke(new Func<object>(delegate { return Handle(req); }));
                            writer.WriteLine(json.Serialize(response));
                        }
                    }
                } catch (Exception) { /* Never terminate KeePass due to a client error. */ }
            }
        }

        private static string Get(Dictionary<string, object> d, string key, string defaultValue = "")
        {
            object o;
            if (d != null && d.TryGetValue(key, out o) && o != null) return Convert.ToString(o);
            return defaultValue;
        }
        private static Dictionary<string, object> Result(bool success, string message)
        {
            return new Dictionary<string, object> { { "ok", success }, { "error", message } };
        }
        private static string SHA256(string s)
        {
            using (SHA256 sha = System.Security.Cryptography.SHA256.Create()) {
                return Convert.ToBase64String(sha.ComputeHash(Encoding.UTF8.GetBytes(s)));
            }
        }
        private bool Authorized(Dictionary<string, object> d)
        {
            string expected = host.CustomConfig.GetString(ConfigName, "");
            string token = Get(d, "token");
            if (expected.Length == 0 || token.Length == 0) return false;
            string actual = SHA256(token);
            if (actual.Length != expected.Length) return false;
            int delta = 0;
            for (int i = 0; i < actual.Length; ++i) delta |= actual[i] ^ expected[i];
            return delta == 0;
        }
        private object Handle(Dictionary<string, object> req)
        {
            try {
                bool unlocked = host.Database != null && host.Database.IsOpen;
                string op = Get(req, "op");
                if (op == "status") return new Dictionary<string, object> {
                    { "ok", true }, { "unlocked", unlocked },
                    { "paired", Authorized(req) },
                    { "database", unlocked ? host.Database.Name : "" }
                };
                if (!unlocked) return Result(false, "KeePass veritabanı kilitli veya kapalı.");
                if (op == "pair") {
                    DialogResult answer = MessageBox.Show(host.MainWindow,
                        "NodeDeck SSH bu açık KeePass veritabanındaki 'SSH Hub' grubuna ve [SSH] kayıtlarına erişmek istiyor.\n\n" +
                        "İzin verirseniz bu kayıtlardaki kullanıcı adları ve parolalar SSH bağlantısında kullanılabilir.\n\n" +
                        "Yalnızca kendi başlattığınız NodeDeck uygulamasına izin verin.",
                        "NodeDeck erişim izni", MessageBoxButtons.YesNo, MessageBoxIcon.Warning);
                    if (answer != DialogResult.Yes) return Result(false, "KeePass erişim izni verilmedi.");
                    byte[] random = new byte[32];
                    using (RandomNumberGenerator rng = RandomNumberGenerator.Create()) rng.GetBytes(random);
                    string token = Convert.ToBase64String(random);
                    host.CustomConfig.SetString(ConfigName, SHA256(token));
                    return new Dictionary<string, object> { { "ok", true }, { "token", token } };
                }
                if (!Authorized(req)) return Result(false, "NodeDeck eşleştirilmemiş. KeePass üzerinden eşleştirin.");
                if (op == "list") return ListEntries();
                if (op == "credential") return Credential(Get(req, "id"));
                if (op == "save") return SaveEntry(req);
                return Result(false, "Bilinmeyen işlem.");
            } catch (Exception ex) { return Result(false, ex.Message); }
        }

        private static string Str(PwEntry entry, string key)
        {
            return entry.Strings.ReadSafe(key);
        }
        private bool IsManaged(PwEntry e)
        {
            if (Str(e, PwDefs.TitleField).StartsWith("[SSH]", StringComparison.OrdinalIgnoreCase)) return true;
            PwGroup g = e.ParentGroup;
            while (g != null) {
                if (g.Name.Equals("SSH Hub", StringComparison.OrdinalIgnoreCase)) return true;
                g = g.ParentGroup;
            }
            return false;
        }
        private IEnumerable<PwEntry> ManagedEntries()
        {
            foreach (PwEntry e in host.Database.RootGroup.GetEntries(true))
                if (IsManaged(e)) yield return e;
        }
        private PwEntry FindManaged(string id)
        {
            foreach (PwEntry e in ManagedEntries())
                if (Convert.ToBase64String(e.Uuid.UuidBytes) == id) return e;
            return null;
        }
        private object ListEntries()
        {
            List<object> results = new List<object>();
            foreach (PwEntry e in ManagedEntries()) {
                string hostName = Str(e, "SSHHost");
                int port = 22;
                int.TryParse(Str(e, "SSHPort"), out port);
                if (port <= 0 || port > 65535) port = 22;
                if (hostName.Length == 0) {
                    Uri uri;
                    if (Uri.TryCreate(Str(e, PwDefs.UrlField), UriKind.Absolute, out uri) && uri.Scheme == "ssh") {
                        hostName = uri.Host;
                        if (!uri.IsDefaultPort) port = uri.Port;
                    }
                }
                if (hostName.Length == 0) continue;
                string title = Str(e, PwDefs.TitleField);
                if (title.StartsWith("[SSH]", StringComparison.OrdinalIgnoreCase)) title = title.Substring(5).Trim();
                string group = Str(e, "SSHGroup");
                if (group.Length == 0) {
                    PwGroup p = e.ParentGroup;
                    group = (p != null && !p.Name.Equals("SSH Hub", StringComparison.OrdinalIgnoreCase)) ? p.Name : "Genel";
                }
                results.Add(new Dictionary<string, object> {
                    { "id", Convert.ToBase64String(e.Uuid.UuidBytes) },
                    { "name", title }, { "host", hostName }, { "port", port },
                    { "username", Str(e, PwDefs.UserNameField) }, { "group", group }
                });
            }
            return new Dictionary<string, object> { { "ok", true }, { "items", results } };
        }
        private object Credential(string id)
        {
            PwEntry e = FindManaged(id);
            if (e == null) return Result(false, "SSH kaydı bulunamadı.");
            return new Dictionary<string, object> { { "ok", true }, { "password", Str(e, PwDefs.PasswordField) } };
        }
        private object SaveEntry(Dictionary<string, object> req)
        {
            string id = Get(req, "id").Trim();
            string name = Get(req, "name").Trim();
            string hostname = Get(req, "host").Trim();
            string username = Get(req, "username").Trim();
            string groupName = Get(req, "group", "Genel").Trim();
            string password = Get(req, "password");
            int port;
            if (!int.TryParse(Get(req, "port", "22"), out port) || port < 1 || port > 65535)
                return Result(false, "Geçersiz SSH portu.");
            if (name.Length < 1 || name.Length > 120 || hostname.Length < 1 || hostname.Length > 253 ||
                username.Length < 1 || username.Length > 120 || groupName.Length > 80)
                return Result(false, "Ad, sunucu, kullanıcı ve grup alanlarını kontrol edin.");
            if (groupName.Length == 0) groupName = "Genel";
            PwDatabase db = host.Database;
            PwEntry e = id.Length > 0 ? FindManaged(id) : null;
            if (id.Length > 0 && e == null) return Result(false, "Düzenlenecek kayıt bulunamadı.");
            PwGroup parent = null;
            foreach (PwGroup g in db.RootGroup.Groups)
                if (g.Name.Equals("SSH Hub", StringComparison.OrdinalIgnoreCase)) { parent = g; break; }
            if (parent == null) { parent = new PwGroup(true, true, "SSH Hub", PwIcon.NetworkServer); db.RootGroup.AddGroup(parent, true); }
            PwGroup child = null;
            foreach (PwGroup g in parent.Groups)
                if (g.Name.Equals(groupName, StringComparison.OrdinalIgnoreCase)) { child = g; break; }
            if (child == null) { child = new PwGroup(true, true, groupName, PwIcon.Folder); parent.AddGroup(child, true); }
            if (e == null) { e = new PwEntry(true, true); child.AddEntry(e, true); }
            else { e.CreateBackup(db); if (e.ParentGroup != child) { e.ParentGroup.Entries.Remove(e); child.AddEntry(e, true); } }
            e.Strings.Set(PwDefs.TitleField, new ProtectedString(false, "[SSH] " + name));
            e.Strings.Set(PwDefs.UserNameField, new ProtectedString(false, username));
            if (id.Length == 0 || password.Length > 0)
                e.Strings.Set(PwDefs.PasswordField, new ProtectedString(true, password));
            string url = "ssh://" + hostname + ":" + port.ToString();
            e.Strings.Set(PwDefs.UrlField, new ProtectedString(false, url));
            e.Strings.Set("SSHHost", new ProtectedString(false, hostname));
            e.Strings.Set("SSHPort", new ProtectedString(false, port.ToString()));
            e.Strings.Set("SSHGroup", new ProtectedString(false, groupName));
            e.Touch(true, false);
            db.Modified = true;
            if (!host.MainWindow.UIFileSave(false)) return Result(false, "KeePass kaydı belleğe ekledi ancak veritabanı kaydedilemedi. KeePass'te elle kaydedin.");
            return new Dictionary<string, object> { { "ok", true }, { "id", Convert.ToBase64String(e.Uuid.UuidBytes) } };
        }
    }
}
