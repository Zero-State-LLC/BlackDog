#!/usr/bin/env bash
# Install the Faust 2.88.0 compiler (no LLVM backend) onto PATH.
# The masked native compile tests need this binary. A machine that already
# has 2.88.0 is left alone.
set -euo pipefail

if command -v sudo >/dev/null 2>&1 && [[ "$(id -u)" -ne 0 ]]; then
  SUDO=sudo
else
  SUDO=
fi

# An absent fallback is not mounted, only checked. On a host where
# /usr/share is mode 0777, a racing user can plant /usr/share/faust
# after that check. Create the directories root-owned and not
# world-writable before any compile.
$SUDO mkdir -p /usr/share/faust /usr/local/share/faust
$SUDO chown root:root /usr/share/faust /usr/local/share/faust
$SUDO chmod 755 /usr/share/faust /usr/local/share/faust

if command -v faust >/dev/null 2>&1; then
  version=$(faust -v 2>&1 || true)
  if [[ "$version" == *"2.88.0"* ]]; then
    echo "Faust 2.88.0 already on PATH"
    exit 0
  fi
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
# Release asset faust-2.88.0.tar.gz (81488527 bytes).
pinned_sha256=e4e175cf236924b5b7d4784cbb8c50cc01e211159e169655dd9e6d8f92b871d9
echo "${pinned_sha256}  ${root}/faust-2.88.0.tar.gz" | sha256sum -c -
tar -xzf "$root/faust-2.88.0.tar.gz" -C "$root"
make -C "$root/faust-2.88.0" compiler -j"$(nproc)"
prefix=${PREFIX:-/usr/local}
$SUDO make -C "$root/faust-2.88.0" install PREFIX="$prefix"
# <prefix>/bin is mode 0777 on GitHub-hosted Ubuntu. An absent
# <prefix>/bin/share/faust or <prefix>/bin/architecture would be refused:
# faust --pathslist names both, and a caller could create either before
# exec. Create them so the sandbox masks them.
$SUDO mkdir -p \
  "$prefix/share/faust" \
  "$prefix/lib/faust" \
  "$prefix/bin/share/faust" \
  "$prefix/bin/architecture"
$SUDO chown root:root \
  "$prefix/share/faust" \
  "$prefix/lib/faust" \
  "$prefix/bin/share/faust" \
  "$prefix/bin/architecture"
$SUDO chmod 755 \
  "$prefix/share/faust" \
  "$prefix/lib/faust" \
  "$prefix/bin/share/faust" \
  "$prefix/bin/architecture"
export PATH="$prefix/bin:${PATH}"
installed=$("$prefix/bin/faust" -v 2>&1 || true)
echo "$installed"
if [[ "$installed" != *"2.88.0"* ]]; then
  echo "installed faust is not 2.88.0" >&2
  exit 1
fi
