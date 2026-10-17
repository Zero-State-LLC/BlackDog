// One-shot libfaust worker. Python spawns this under the sandbox and writes
// the request on stdin: {"source": "...", "lang": "wasm"|"cpp", "options": []}.
// Results land in <workdir>/result.json plus output.* files. The process
// refuses to start unless FAUSTCODER_SANDBOX=1 and Node's permission model
// is on, so a bare `node compile.mjs` does not compile.

import { writeFileSync, renameSync } from "node:fs";
import { join } from "node:path";
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

async function compileWasm(compiler, source, options) {
  const factory = await compiler.createMonoDSPFactory("input", source, options.join(" "));
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

function compileCpp(compiler, source, options) {
  const args = ["-lang", "cpp", "-o", "output.cpp", ...options].join(" ");
  const ok = compiler.generateAuxFiles("input", source, args);
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
  const compiler = await loadCompiler(join(workdir, "runtime", "libfaust-wasm.js"));
  const libfaustVersion = compiler.version();
  let compiled;
  try {
    compiled =
      request.lang === "wasm"
        ? await compileWasm(compiler, request.source, options)
        : compileCpp(compiler, request.source, options);
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
    compile_ok: compiled.compile_ok,
    diagnostics: compiled.diagnostics,
    output_files: outputFiles,
  });
}

await main();
