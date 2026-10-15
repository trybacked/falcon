#!/usr/bin/env bash
# End-user installer: symlink falcon into /usr/local/bin (optional).
set -euo pipefail
dir="$(cd "$(dirname "$0")" && pwd)"
bin="$dir/bin"
if [[ ! -x "$bin/falcon" ]]; then
  echo "Missing $bin/falcon — unzip the full Falcon-macos archive." >&2
  exit 1
fi
target="/usr/local/bin/falcon"
echo "Install Falcon CLI to $target (requires sudo)."
sudo ln -sf "$bin/falcon" "$target"
if [[ -x "$bin/falcon-recorder" ]]; then
  sudo ln -sf "$bin/falcon-recorder" "/usr/local/bin/falcon-recorder"
fi
echo "Installed. Run: falcon --help"
echo "Sessions default folder: ./sessions (see config.toml.example in $dir)"
