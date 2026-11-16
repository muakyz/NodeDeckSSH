# Compiles the KeePass 2 plugin against the KeePass version installed on THIS computer.
# Usage: powershell -ExecutionPolicy Bypass -File .\install_keepass_bridge.ps1 [-KeePassExe "C:\...\KeePass.exe"]
param([string]$KeePassExe = "")
$ErrorActionPreference = "Stop"
$base = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($KeePassExe)) {
    $paths = @(
        "$env:ProgramFiles\KeePass Password Safe 2\KeePass.exe",
        "${env:ProgramFiles(x86)}\KeePass Password Safe 2\KeePass.exe",
        "$env:ProgramFiles\KeePass\KeePass.exe",
        "${env:ProgramFiles(x86)}\KeePass\KeePass.exe"
    )
    $KeePassExe = $paths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $KeePassExe -or -not (Test-Path -LiteralPath $KeePassExe)) {
    $KeePassExe = Read-Host "KeePass.exe tam dosya yolunu girin"
}
if (-not (Test-Path -LiteralPath $KeePassExe)) { throw "KeePass.exe bulunamadi: $KeePassExe" }
$dir = Split-Path -Parent $KeePassExe
$lib = Join-Path $dir "KeePassLib.dll"
if (-not (Test-Path $lib)) { throw "KeePassLib.dll bulunamadi. KeePass 2.x kurulumu gerekli." }
$csc = "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { throw ".NET Framework 4.x C# compiler (csc.exe) bulunamadi." }
$output = Join-Path $base "NodeDeckBridge.dll"
$source = Join-Path $base "keepass-bridge\NodeDeckBridge.cs"
Write-Host "[1/3] KeePass: $KeePassExe" -ForegroundColor Cyan
Write-Host "[2/3] KeePass eklentisi derleniyor..." -ForegroundColor Cyan
& $csc /nologo /target:library /optimize+ "/out:$output" "/reference:$KeePassExe" "/reference:$lib" /reference:System.dll /reference:System.Core.dll /reference:System.Web.Extensions.dll /reference:System.Windows.Forms.dll "$source"
if ($LASTEXITCODE -ne 0) { throw "Eklenti derlenemedi. Derleyicinin hata mesajlarini kontrol edin." }
$folder = Join-Path $dir "Plugins"
if (-not (Test-Path $folder)) { New-Item -ItemType Directory -Path $folder | Out-Null }
Write-Host "[3/3] Eklenti KeePass Plugins klasorune kopyalaniyor..." -ForegroundColor Cyan
Copy-Item -LiteralPath $output -Destination (Join-Path $folder "NodeDeckBridge.dll") -Force
Write-Host "Basarili. KeePass'i tamamen kapatip yeniden acin." -ForegroundColor Green
Write-Host "KeePass -> Tools -> Plugins bolumunde NodeDeckBridge eklentisi gorunmeli."
