// One-shot libfaust worker. Python spawns this under the sandbox and writes
// the request on stdin: {"source": "...", "lang": "wasm"|"cpp", "options": []}.
// Results land in <workdir>/result.json plus output.* files. The process
// refuses to start unless FAUSTCODER_SANDBOX=1 and Node's permission model
// is on, so a bare `node compile.mjs` does not compile.

import { createHash } from "node:crypto";
import { writeFileSync, renameSync, readdirSync, readFileSync, statSync } from "node:fs";
import { connect } from "node:net";
import { join, relative } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

const FAUSTWASM_VERSION = "0.19.0";
const MAX_STDIN = 2 * 1024 * 1024;
const SAFE_OPTION = /^(-[a-z][a-z0-9]*|[0-9]+)$/;

function failClosed(message) {
  process.stderr.write(`${message}\n`);
  process.exit(2);
}

function writeResult(workdir, body) {
  const destination = join(workdir, "result.json");
  const temporary = `${destination}.tmp`;
  writeFileSync(temporary, JSON.stringify(body));
  renameSync(temporary, destination);
}

async function readStdin() {
  const chunks = [];
  let size = 0;
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > MAX_STDIN) {
      failClosed("stdin exceeds the worker cap");
    }
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}

function assertOptions(options) {
  if (!Array.isArray(options)) {
    failClosed("options must be an array");
  }
  for (const option of options) {
    if (typeof option !== "string" || !SAFE_OPTION.test(option) || option.length > 32) {
      failClosed("rejected compiler option");
    }
  }
}

function ensureVirtualDir(fs, path) {
  const parts = path.split("/").filter(Boolean);
  let acc = "";
  for (const part of parts) {
    acc += `/${part}`;
    if (!fs.analyzePath(acc).exists) {
      fs.mkdir(acc);
    }
  }
}

function clearVirtual(fs, dir) {
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
      const stat = statSync(path);
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

function stageLibraries(compiler, root) {
  const fs = compiler.fs();
  clearVirtual(fs, "/usr/share/faust");
  ensureVirtualDir(fs, "/usr/share/faust");
  for (const file of hostLibraries(root)) {
    const rel = relative(root, file).split("\\").join("/");
    const dest = `/usr/share/faust/${rel}`;
    ensureVirtualDir(fs, dest.split("/").slice(0, -1).join("/"));
    fs.writeFile(dest, readFileSync(file));
  }
}

function mountedLibrarySha256(fs) {
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
  files.sort((left, right) => (left[0] < right[0] ? -1 : left[0] > right[0] ? 1 : 0));
  const hash = createHash("sha256");
  for (const [rel, body] of files) {
    const length = Buffer.alloc(8);
    length.writeBigUInt64BE(BigInt(body.length));
    hash.update(Buffer.from(rel, "utf8"));
    hash.update(Buffer.from("\n"));
    hash.update(length);
    hash.update(body);
  }
  return hash.digest("hex");
}

function namespaceInterfaces() {
  let text;
  try {
    text = readFileSync("/proc/net/dev", "utf8");
  } catch {
    failClosed("network namespace interfaces could not be read");
  }
  const names = [];
  for (const line of text.split("\n").slice(2)) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }
    const name = trimmed.split(":")[0];
    if (name) {
      names.push(name);
    }
  }
  return names;
}

function assertNetworkIsolated() {
  const names = namespaceInterfaces();
  if (names.length !== 1 || names[0] !== "lo") {
    failClosed("network namespace has a non-loopback interface");
  }
  return new Promise((resolve) => {
    const socket = connect({ host: "1.1.1.1", port: 443 });
    const timer = setTimeout(() => {
      socket.destroy();
      failClosed("network connect did not fail inside the sandbox");
    }, 1000);
    socket.once("error", () => {
      clearTimeout(timer);
      socket.destroy();
      resolve();
    });
    socket.once("connect", () => {
      clearTimeout(timer);
      socket.destroy();
      failClosed("network connect succeeded inside the sandbox");
    });
  });
}

function assertSourcePath(path) {
  if (typeof path !== "string" || path === "" || path.startsWith("/") || path.includes("\\")) {
    failClosed("source path is not relative");
  }
  const parts = path.split("/");
  for (const part of parts) {
    if (part === "" || part === "." || part === "..") {
      failClosed("source path escapes the source directory");
    }
    if (!/^[A-Za-z0-9_.+-]+$/.test(part)) {
      failClosed("source path has an unsafe component");
    }
  }
  if (!path.endsWith(".dsp")) {
    failClosed("source path must be a .dsp file");
  }
}

function stageSources(compiler, sources) {
  const fs = compiler.fs();
  clearVirtual(fs, "/src");
  ensureVirtualDir(fs, "/src");
  for (const file of sources) {
    if (!file || typeof file.source !== "string") {
      failClosed("source file must be a string");
    }
    assertSourcePath(file.path);
    const dest = `/src/${file.path}`;
    ensureVirtualDir(fs, dest.split("/").slice(0, -1).join("/"));
    fs.writeFile(dest, file.source);
  }
}

async function loadCompiler(runtimeJs) {
  const entry = fileURLToPath(
    new URL("./node_modules/@grame/faustwasm/dist/esm/index.js", import.meta.url),
  );
  const faustwasm = await import(pathToFileURL(entry).href);
  const faustModule = await faustwasm.instantiateFaustModuleFromFile(runtimeJs);
  const compiler = new faustwasm.FaustCompiler(new faustwasm.LibFaust(faustModule));
  return compiler;
}

function hostBytes(value) {
  if (typeof value === "string") {
    return Buffer.from(value, "utf8");
  }
  return Buffer.from(value);
}

async function compileWasm(compiler, moduleName, source, options) {
  const factory = await compiler.createMonoDSPFactory(moduleName, source, options.join(" "));
  if (!factory || !factory.code) {
    return { compile_ok: false, diagnostics: "compiler returned failure\n", files: [] };
  }
  return {
    compile_ok: true,
    diagnostics: "",
    files: [
      ["output.wasm", Buffer.from(factory.code)],
      ["output.json", Buffer.from(factory.json, "utf8")],
    ],
  };
}

function compileCpp(compiler, moduleName, source, options) {
  const args = ["-lang", "cpp", "-o", "output.cpp", ...options].join(" ");
  const ok = compiler.generateAuxFiles(moduleName, source, args);
  if (!ok) {
    const message = compiler.getErrorMessage() || "compiler returned failure\n";
    return {
      compile_ok: false,
      diagnostics: message.endsWith("\n") ? message : `${message}\n`,
      files: [],
    };
  }
  const bytes = hostBytes(compiler.fs().readFile("/output.cpp"));
  return { compile_ok: true, diagnostics: "", files: [["output.cpp", bytes]] };
}

async function main() {
  if (process.env.FAUSTCODER_SANDBOX !== "1" || process.permission === undefined) {
    failClosed("refusing to compile without the FaustCoder sandbox");
  }
  const workdir = process.argv[2];
  if (!workdir) {
    failClosed("workdir argument is required");
  }
  let request;
  try {
    request = JSON.parse(await readStdin());
  } catch {
    failClosed("request is not JSON");
  }
  if (!request || typeof request.source !== "string") {
    failClosed("source must be a string");
  }
  if (request.lang !== "wasm" && request.lang !== "cpp") {
    failClosed("lang must be wasm or cpp");
  }
  const options = request.options ?? [];
  assertOptions(options);
  const libraryRoot = process.argv[3];
  if (!libraryRoot) {
    failClosed("library tree argument is required");
  }
  const sources = request.sources ?? [];
  if (!Array.isArray(sources)) {
    failClosed("sources must be an array");
  }
  await assertNetworkIsolated();
  const compiler = await loadCompiler(join(workdir, "runtime", "libfaust-wasm.js"));
  stageLibraries(compiler, libraryRoot);
  const libraryTreeSha256 = mountedLibrarySha256(compiler.fs());
  let moduleName = "input";
  if (sources.length > 0) {
    if (typeof request.filename !== "string") {
      failClosed("filename is required");
    }
    assertSourcePath(request.filename);
    stageSources(compiler, sources);
    moduleName = `/src/${request.filename}`;
  }
  const libfaustVersion = compiler.version();
  let compiled;
  try {
    compiled =
      request.lang === "wasm"
        ? await compileWasm(compiler, moduleName, request.source, options)
        : compileCpp(compiler, moduleName, request.source, options);
  } catch (error) {
    const message = error instanceof Error ? error.message : "compiler failed";
    compiled = {
      compile_ok: false,
      diagnostics: message.endsWith("\n") ? message : `${message}\n`,
      files: [],
    };
  }
  const outputFiles = [];
  for (const [name, bytes] of compiled.files) {
    if (!/^output\.[a-z0-9]+$/.test(name)) {
      failClosed("unexpected output name");
    }
    writeFileSync(join(workdir, name), bytes);
    outputFiles.push(name);
  }
  writeResult(workdir, {
    faustwasm_version: FAUSTWASM_VERSION,
    libfaust_version: libfaustVersion,
    library_tree_sha256: libraryTreeSha256,
    compile_ok: compiled.compile_ok,
    diagnostics: compiled.diagnostics,
    output_files: outputFiles,
  });
}

await main();
