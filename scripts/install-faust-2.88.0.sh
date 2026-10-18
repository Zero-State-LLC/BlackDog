#!/usr/bin/env bash
# Install the Faust 2.88.0 compiler (no LLVM backend) onto PATH.
# The masked native compile tests need this binary. A machine that already
# has 2.88.0 is left alone.
set -euo pipefail

if command -v faust >/dev/null 2>&1; then
  version=$(faust -v 2>&1 || true)
  if [[ "$version" == *"2.88.0"* ]]; then
    echo "Faust 2.88.0 already on PATH"
    exit 0
  fi
fi

if command -v sudo >/dev/null 2>&1 && [[ "$(id -u)" -ne 0 ]]; then
  SUDO=sudo
else
  SUDO=
fi

$SUDO apt-get update
$SUDO apt-get install -y --no-install-recommends build-essential cmake ca-certificates curl

probe=$(mktemp)
if ! echo 'int main(){return 0;}' | c++ -x c++ - -o "$probe" >/dev/null 2>&1; then
  export CC="${CC:-gcc}"
  export CXX="${CXX:-g++}"
fi
rm -f "$probe"

root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
curl -fsSL -o "$root/faust-2.88.0.tar.gz" \
  https://github.com/grame-cncm/faust/releases/download/2.88.0/faust-2.88.0.tar.gz
tar -xzf "$root/faust-2.88.0.tar.gz" -C "$root"
make -C "$root/faust-2.88.0" compiler -j"$(nproc)"
prefix=${PREFIX:-/usr/local}
$SUDO make -C "$root/faust-2.88.0" install PREFIX="$prefix"
export PATH="$prefix/bin:${PATH}"
installed=$("$prefix/bin/faust" -v 2>&1 || true)
echo "$installed"
if [[ "$installed" != *"2.88.0"* ]]; then
  echo "installed faust is not 2.88.0" >&2
  exit 1
fi
