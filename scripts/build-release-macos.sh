#!/usr/bin/env bash
# Build a portable Falcon folder for macOS (no uv/pip for end users).
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

arch="$(uname -m)"
out="dist/Falcon-macos-${arch}"

echo "==> Sync Python + build tools"
uv sync --group dev --group build

echo "==> Swift recorder (release)"
swift build -c release --package-path packages/platform-macos

echo "==> PyInstaller"
rm -rf build dist/falcon "$out"
uv run pyinstaller --noconfirm --distpath dist --workpath build scripts/falcon.spec

mkdir -p "$out/bin"
cp -R dist/falcon/. "$out/bin/"
cp packages/platform-macos/.build/release/falcon-recorder "$out/bin/falcon-recorder"
chmod +x "$out/bin/falcon" "$out/bin/falcon-recorder"
cp config.toml.example "$out/config.toml.example"
cp scripts/user-README.txt "$out/README.txt"
cp scripts/install-macos.sh "$out/Install.command"
chmod +x "$out/Install.command"

(
  cd dist
  rm -f "Falcon-macos-${arch}.zip"
  zip -r "Falcon-macos-${arch}.zip" "Falcon-macos-${arch}"
)

echo "Done: $out"
echo "Zip:  dist/Falcon-macos-${arch}.zip"
