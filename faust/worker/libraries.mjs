// Shared pinned-library staging for compiler and renderer. No host filesystem mount.
import { createHash } from "node:crypto";
import { readdirSync, readFileSync, lstatSync } from "node:fs";
import { join, relative } from "node:path";
function failClosed(message) { throw new Error(message); }

export function ensureVirtualDir(fs, path) {
  const parts = path.split("/").filter(Boolean);
  let acc = "";
  for (const part of parts) {
    acc += `/${part}`;
    if (!fs.analyzePath(acc).exists) {
      fs.mkdir(acc);
    }
  }
}

export function clearVirtual(fs, dir) {
  let names;
  try {
    names = fs.readdir(dir);
  } catch {
    return;
  }
  for (const name of names) {
    if (name === "." || name === "..") {
      continue;
    }
    const path = `${dir}/${name}`;
    const info = fs.analyzePath(path);
    if (info.object && info.object.isFolder) {
      clearVirtual(fs, path);
      fs.rmdir(path);
    } else {
      fs.unlink(path);
    }
  }
}

function hostLibraries(root) {
  const files = [];
  const walk = (dir) => {
    for (const name of readdirSync(dir)) {
      if (name.startsWith(".")) {
        continue;
      }
      const path = join(dir, name);
      const stat = lstatSync(path);
      if (stat.isSymbolicLink()) {
        failClosed("library tree contains a symlink");
      }
      if (stat.isDirectory()) {
        walk(path);
      } else if (stat.isFile() && name.endsWith(".lib")) {
        files.push(path);
      }
    }
  };
  walk(root);
  return files;
}

function libraryTreeSha256(entries) {
  const files = entries.slice().sort((left, right) => (left[0] < right[0] ? -1 : left[0] > right[0] ? 1 : 0));
  const hash = createHash("sha256");
  for (const [rel, raw] of files) {
    const body = Buffer.isBuffer(raw) ? raw : Buffer.from(raw);
    const length = Buffer.alloc(8);
    length.writeBigUInt64BE(BigInt(body.length));
    hash.update(Buffer.from(rel, "utf8"));
    hash.update(Buffer.from("\n"));
    hash.update(length);
    hash.update(body);
  }
  return hash.digest("hex");
}

export function stageLibraries(compiler, root) {
  const fs = compiler.fs();
  clearVirtual(fs, "/usr/share/faust");
  ensureVirtualDir(fs, "/usr/share/faust");
  const written = [];
  for (const file of hostLibraries(root)) {
    const rel = relative(root, file).split("\\").join("/");
    const dest = `/usr/share/faust/${rel}`;
    ensureVirtualDir(fs, dest.split("/").slice(0, -1).join("/"));
    const bytes = readFileSync(file);
    fs.writeFile(dest, bytes);
    written.push([rel, bytes]);
  }
  return libraryTreeSha256(written);
}

export function mountedLibrarySha256(fs) {
  const files = [];
  const walk = (dir, prefix) => {
    let names;
    try {
      names = fs.readdir(dir);
    } catch {
      failClosed("mounted library tree is missing");
    }
    for (const name of names) {
      if (name === "." || name === ".." || name.startsWith(".")) {
        continue;
      }
      const path = `${dir}/${name}`;
      const rel = prefix ? `${prefix}/${name}` : name;
      const info = fs.analyzePath(path);
      if (info.object && info.object.isFolder) {
        walk(path, rel);
      } else if (name.endsWith(".lib")) {
        const data = fs.readFile(path);
        files.push([rel, Buffer.from(data)]);
      }
    }
  };
  walk("/usr/share/faust", "");
  return libraryTreeSha256(files);
}
