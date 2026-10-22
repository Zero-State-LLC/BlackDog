// One-shot libfaust worker. Python spawns this under the sandbox and writes
// the request on stdin: {"source": "...", "lang": "wasm"|"cpp", "options": []}.
// Results land in <workdir>/result.json plus output.* files. The process
// refuses to start unless FAUSTCODER_SANDBOX=1 and Node's permission model
// is on, so a bare `node compile.mjs` does not compile.

import { writeFileSync, renameSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";
import { assertNetworkIsolated } from "./netns-canary.mjs";
import { terminationFields } from "./termination.mjs";

import { ensureVirtualDir, clearVirtual, stageLibraries, mountedLibrarySha256 } from "./libraries.mjs";

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
  const writtenSha = stageLibraries(compiler, libraryRoot);
  const libraryTreeSha256 = mountedLibrarySha256(compiler.fs());
  if (writtenSha !== libraryTreeSha256) {
    failClosed("mounted library tree does not match the bytes written");
  }
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
    const termination = terminationFields(error);
    compiled = {
      compile_ok: false,
      diagnostics: message.endsWith("\n") ? message : `${message}\n`,
      files: [],
      runtime_stack_overflow: termination.runtime_stack_overflow,
      wasm_trap: termination.wasm_trap,
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
    runtime_stack_overflow: compiled.runtime_stack_overflow === true,
    wasm_trap: typeof compiled.wasm_trap === "string" ? compiled.wasm_trap : null,
  });
}

await main();
