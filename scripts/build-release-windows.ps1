# Build portable Falcon for Windows (no uv/pip for end users).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$out = Join-Path $root "dist\Falcon-win64"

Write-Host "==> Sync Python + build tools + win32"
uv sync --group dev --group build --extra win32

Write-Host "==> PyInstaller"
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
if (Test-Path "dist\falcon") { Remove-Item -Recurse -Force "dist\falcon" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }

uv run pyinstaller --noconfirm --distpath dist --workpath build scripts/falcon.spec

New-Item -ItemType Directory -Force -Path (Join-Path $out "bin") | Out-Null
Copy-Item -Recurse -Force "dist\falcon\*" (Join-Path $out "bin")
Copy-Item "config.toml.example" (Join-Path $out "config.toml.example")
Copy-Item "scripts\user-README.txt" (Join-Path $out "README.txt")
Copy-Item "scripts\install-windows.ps1" (Join-Path $out "Install.ps1")

Compress-Archive -Force -Path $out -DestinationPath "dist\Falcon-win64.zip"

Write-Host "Done: $out"
Write-Host "Zip:  dist\Falcon-win64.zip"
