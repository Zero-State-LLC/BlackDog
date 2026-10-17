#!/usr/bin/env bash
# Fetch Faust 2.88.0 examples for the multi-file and stack-size checks.
# The sources are not committed. The compiler sandbox does not download them.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
dest=$root/faust/examples/2.88.0
marker=$dest/physicalModeling/fds/2dKirchhoffThinPlate.dsp
if [[ -f "$marker" && -f "$dest/misc/mixer.dsp" && -f "$dest/physicalModeling/faust-stk/bass.dsp" ]]; then
  exit 0
fi
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
curl -fsSL -o "$tmpdir/faust.tar.gz" "https://codeload.github.com/grame-cncm/faust/tar.gz/refs/tags/2.88.0"
tar -xzf "$tmpdir/faust.tar.gz" -C "$tmpdir"
src=$(find "$tmpdir" -mindepth 1 -maxdepth 1 -type d -name 'faust-*')
if [[ ! -d "$src/examples" ]]; then
  echo "Faust 2.88.0 archive did not contain examples" >&2
  exit 1
fi
rm -rf "$dest"
mkdir -p "$(dirname "$dest")"
mv "$src/examples" "$dest"
test -s "$marker"
