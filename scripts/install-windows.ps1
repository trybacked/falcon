# Add Falcon bin folder to the current user PATH (Windows).
$ErrorActionPreference = "Stop"
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$bin = Join-Path $dir "bin"
if (-not (Test-Path (Join-Path $bin "falcon.exe"))) {
  throw "Missing falcon.exe in $bin"
}
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$bin*") {
  [Environment]::SetEnvironmentVariable("Path", "$bin;$userPath", "User")
  Write-Host "Added to user PATH: $bin"
} else {
  Write-Host "Already on PATH: $bin"
}
Write-Host "Open a new terminal, then: falcon --help"
