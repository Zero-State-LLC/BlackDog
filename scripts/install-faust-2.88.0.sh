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

# Refuse a directory that is not a real root-owned directory, or that
# is group- or world-writable unless it is root-owned and sticky.
# stat without -L does not follow a symlink. A symlink is refused.
refuse_unless_root_only() {
  local path=$1
  local mode uid other group sticky
  if [[ -L $path ]]; then
    echo "refusing symlink in directory chain: $path" >&2
    exit 1
  fi
  if [[ ! -d $path ]]; then
    echo "refusing non-directory in directory chain: $path" >&2
    exit 1
  fi
  mode=$(stat -c '%a' -- "$path")
  uid=$(stat -c '%u' -- "$path")
  other=$((10#$mode % 10))
  group=$((10#$mode / 10 % 10))
  sticky=$((10#$mode / 1000))
  if (( (other & 2) != 0 && ((sticky & 1) == 0 || uid != 0) )); then
    echo "refusing world-writable parent without a root-owned sticky bit: $path" >&2
    exit 1
  fi
  if [[ $uid != "0" ]]; then
    echo "refusing non-root directory: $path" >&2
    exit 1
  fi
  if (( (group & 2) != 0 && (sticky & 1) == 0 )); then
    echo "refusing group-writable directory: $path" >&2
    exit 1
  fi
}

# Every component from path up to / must be root-only. A root-owned
# sticky directory is allowed. A user-owned grandparent is not.
walk_root_only_chain() {
  local current=$1
  while true; do
    refuse_unless_root_only "$current"
    if [[ $current == "/" ]]; then
      break
    fi
    current=$(dirname -- "$current")
  done
}

# chmod through a directory fd opened with O_NOFOLLOW. A symlink swapped
# in before chmod is refused, and the link target is not mode-changed.
chmod_directory_nofollow() {
  local path=$1
  $SUDO python3 -c 'import os, sys
path = sys.argv[1]
fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
try:
    os.fchmod(fd, 0o755)
finally:
    os.close(fd)
' "$path"
}

# Create one real root-owned directory, mode 0755, without following a
# pre-seeded symlink. The parent chain up to / must already exist and
# be root-only. A pre-existing path is refused unless it is already a
# real root-owned directory mode 0755: an attacker-owned directory is
# not chowned, so its planted contents are not adopted.
ensure_root_dir() {
  local path=$1
  local parent owner kind mode
  if [[ -z $path || $path == "/" ]]; then
    echo "refusing to create $path" >&2
    exit 1
  fi
  parent=$(dirname -- "$path")
  if [[ -L $parent ]]; then
    echo "refusing symlink parent: $parent" >&2
    exit 1
  fi
  if [[ ! -d $parent ]]; then
    echo "refusing missing parent: $parent" >&2
    exit 1
  fi
  walk_root_only_chain "$parent"
  if [[ -L $path ]]; then
    echo "refusing pre-seeded symlink: $path" >&2
    exit 1
  fi
  if [[ -e $path && ! -d $path ]]; then
    echo "refusing non-directory: $path" >&2
    exit 1
  fi
  if [[ -d $path ]]; then
    owner=$(stat -c '%u' -- "$path")
    kind=$(stat -c '%F' -- "$path")
    mode=$(stat -c '%a' -- "$path")
    if [[ $owner != "0" || $kind != "directory" || $mode != "755" ]]; then
      echo "refusing pre-existing path: $path" >&2
      exit 1
    fi
    return 0
  fi
  $SUDO mkdir -- "$path"
  if [[ -L $path || ! -d $path ]]; then
    echo "refusing: $path is not a real directory" >&2
    exit 1
  fi
  $SUDO chown -h root:root -- "$path"
  if [[ -L $path || ! -d $path ]]; then
    echo "refusing: $path is not a real directory after chown" >&2
    exit 1
  fi
  if ! chmod_directory_nofollow "$path"; then
    echo "refusing: $path is not a real directory after chmod" >&2
    exit 1
  fi
  if [[ -L $path ]]; then
    echo "refusing: $path is not a real directory after chmod" >&2
    exit 1
  fi
  owner=$(stat -c '%u' -- "$path")
  kind=$(stat -c '%F' -- "$path")
  mode=$(stat -c '%a' -- "$path")
  if [[ $owner != "0" || $kind != "directory" || $mode != "755" ]]; then
    echo "refusing: $path is not a root-owned directory mode 0755" >&2
    exit 1
  fi
}

# Create path and any missing parents. Each component is ensure_root_dir.
ensure_root_tree() {
  local path=$1
  local parent
  if [[ -z $path || $path == "/" ]]; then
    echo "refusing to create $path" >&2
    exit 1
  fi
  parent=$(dirname -- "$path")
  if [[ $parent != "/" && ( -L $parent || ! -d $parent ) ]]; then
    ensure_root_tree "$parent"
  fi
  ensure_root_dir "$path"
}

# Tests source this file to call ensure_root_dir. The install runs only
# when the file is executed.
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  return 0
fi

# An absent fallback is not mounted, only checked. On a host where
# /usr/share is mode 0777, a racing user can plant /usr/share/faust
# after that check. Create the directories root-owned and not
# world-writable before any compile.
ensure_root_tree /usr/share/faust
ensure_root_tree /usr/local/share/faust

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
# exec. Create them so the sandbox masks them. A pre-seeded symlink, a
# non-directory, or a world-writable parent without the sticky bit is
# refused. chown -h does not follow a link.
ensure_root_tree "$prefix/share/faust"
ensure_root_tree "$prefix/lib/faust"
ensure_root_tree "$prefix/bin/share/faust"
ensure_root_tree "$prefix/bin/architecture"
export PATH="$prefix/bin:${PATH}"
installed=$("$prefix/bin/faust" -v 2>&1 || true)
echo "$installed"
if [[ "$installed" != *"2.88.0"* ]]; then
  echo "installed faust is not 2.88.0" >&2
  exit 1
fi
