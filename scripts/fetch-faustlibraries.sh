#!/usr/bin/env bash
# Fetch faustlibraries commit 2edec0537f53 and refuse a tree whose sha256 differs.
# The download runs on the host. The compiler sandbox has no network.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
dest=${FAUSTCODER_LIBRARIES:-$root/faust/libraries/2edec0537f53}
commit=2edec0537f53
url="https://github.com/grame-cncm/faustlibraries/archive/${commit}.tar.gz"

verify() {
  python3 -c 'from faustcoder.libraries import main; main()'
}
if verify >/dev/null 2>&1; then
  verify
  exit 0
fi

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
curl -fsSL -o "$tmpdir/libs.tar.gz" "$url"
tar -xzf "$tmpdir/libs.tar.gz" -C "$tmpdir"
src=$(find "$tmpdir" -mindepth 1 -maxdepth 1 -type d -name 'faustlibraries-*')
if [[ -z "$src" || ! -f "$src/version.lib" ]]; then
  echo "faustlibraries archive did not contain version.lib" >&2
  exit 1
fi
rm -rf "$dest"
mkdir -p "$(dirname "$dest")"
mv "$src" "$dest"
verify
