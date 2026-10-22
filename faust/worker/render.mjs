// One-shot offline renderer. Python spawns this under the same sandbox as
// compile.mjs and writes the request on stdin:
// {"source","options","sample_rate","block_size","frames","stimuli","press_buttons_first_block"}.
// Stimulus files are inputs/<name>.f32 (mono little-endian float32).
// Output is out-<name>.f32 (planar little-endian float32, channel then frame)
// plus result.json. The process refuses to start unless FAUSTCODER_SANDBOX=1
// and Node's permission model is on.

import { readFileSync, writeFileSync, renameSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";
import { assertNetworkIsolated } from "./netns-canary.mjs";
import { terminationFields } from "./termination.mjs";

import { stageLibraries, mountedLibrarySha256 } from "./libraries.mjs";

const FAUSTWASM_VERSION = "0.19.0";
const MAX_STDIN = 2 * 1024 * 1024;
const SAFE_OPTION = /^(-[a-z][a-z0-9]*|[0-9]+)$/;
// Keep in step with faustcoder.signal.KNOWN_STIMULI.
const STIMULI = new Set([
  "impulse",
  "sine",
  "noise",
  "ess",
  "sine_997_m1",
  "sine_997_m20",
  "smpte",
  "noise_m12",
  "noise_m30",
  "dc_step",
]);

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
  return { faustwasm, compiler };
}

function readMono(workdir, name, frames) {
  const bytes = readFileSync(join(workdir, "inputs", `${name}.f32`));
  if (bytes.length !== frames * 4) {
    failClosed(`stimulus ${name} has ${bytes.length} bytes`);
  }
  return new Float32Array(bytes.buffer, bytes.byteOffset, frames);
}

function planarBytes(channels) {
  const frames = channels[0].length;
  const out = Buffer.alloc(channels.length * frames * 4);
  let offset = 0;
  for (const channel of channels) {
    Buffer.from(channel.buffer, channel.byteOffset, channel.byteLength).copy(out, offset);
    offset += channel.byteLength;
  }
  return out;
}

function buttonsOf(proc) {
  const found = [];
  const pending = [...(proc.getDescriptors() || [])];
  while (pending.length) {
    const item = pending.shift();
    if (!item || typeof item !== "object") continue;
    if (Array.isArray(item.items)) pending.push(...item.items);
    if (item.type === "button" && typeof item.address === "string") found.push(item.address);
  }
  return found;
}

function renderOne(proc, mono, frames, blockSize, buttons, pressFirst) {
  const inputs = proc.getNumInputs();
  const outputs = proc.getNumOutputs();
  if (outputs < 1) {
    throw new Error("renderer produced no outputs");
  }
  const rendered = Array.from({ length: outputs }, () => new Float32Array(frames));
  proc.start();
  for (let offset = 0; offset < frames; offset += blockSize) {
    const press = pressFirst && offset === 0;
    for (const address of buttons) {
      proc.setParamValue(address, press ? 1 : 0);
    }
    const blockIn = [];
    if (inputs > 0) {
      const slice = mono.subarray(offset, offset + blockSize);
      for (let channel = 0; channel < inputs; channel += 1) blockIn.push(slice);
    }
    const blockOut = Array.from({ length: outputs }, () => new Float32Array(blockSize));
    const ok = proc.compute(blockIn, blockOut);
    if (!ok) throw new Error("compute returned false");
    for (let channel = 0; channel < outputs; channel += 1) {
      rendered[channel].set(blockOut[channel], offset);
    }
  }
  proc.stop();
  return rendered;
}

async function main() {
  if (process.env.FAUSTCODER_SANDBOX !== "1" || process.permission === undefined) {
    failClosed("refusing to render without the FaustCoder sandbox");
  }
  await assertNetworkIsolated();
  const workdir = process.argv[2];
  if (!workdir) failClosed("workdir argument is required");
  let request;
  try {
    request = JSON.parse(await readStdin());
  } catch {
    failClosed("request is not JSON");
  }
  if (!request || typeof request.source !== "string") failClosed("source must be a string");
  const options = request.options ?? [];
  assertOptions(options);
  const sampleRate = request.sample_rate;
  const blockSize = request.block_size;
  const frames = request.frames;
  const stimuli = request.stimuli;
  if (sampleRate !== 44100 && sampleRate !== 48000) failClosed("sample_rate is not 44100 or 48000");
  if (!Number.isInteger(blockSize) || blockSize < 1 || blockSize > 4096) {
    failClosed("block_size is out of range");
  }
  // Same cap as faustcoder.signal.MAX_FRAMES (3 s at 48 kHz).
  if (!Number.isInteger(frames) || frames < blockSize || frames > 144000 || frames % blockSize !== 0) {
    failClosed("frames are out of range");
  }
  if (!Array.isArray(stimuli) || stimuli.length === 0) failClosed("stimuli are required");
  for (const name of stimuli) {
    if (typeof name !== "string" || !STIMULI.has(name)) failClosed("unknown stimulus");
  }
  const pressFirst = request.press_buttons_first_block !== false;
  const { faustwasm, compiler } = await loadCompiler(join(workdir, "runtime", "libfaust-wasm.js"));
  const libraryRoot = process.argv[3];
  if (!libraryRoot) failClosed("library tree argument is required");
  const writtenSha = stageLibraries(compiler, libraryRoot);
  const libraryTreeSha256 = mountedLibrarySha256(compiler.fs());
  if (writtenSha !== libraryTreeSha256) failClosed("mounted library tree does not match the bytes written");
  const libfaustVersion = compiler.version();
  const generator = new faustwasm.FaustMonoDspGenerator();
  let compiled;
  try {
    compiled = await generator.compile(compiler, "input", request.source, options.join(" "));
  } catch (error) {
    const message = error instanceof Error ? error.message : "compiler failed";
    const termination = terminationFields(error);
    writeResult(workdir, {
      faustwasm_version: FAUSTWASM_VERSION,
      libfaust_version: libfaustVersion,
      library_tree_sha256: libraryTreeSha256,
      compile_ok: false,
      diagnostics: message.endsWith("\n") ? message : `${message}\n`,
      inputs: 0,
      outputs: 0,
      stimuli: [],
      runtime_stack_overflow: termination.runtime_stack_overflow,
      wasm_trap: termination.wasm_trap,
    });
    return;
  }
  if (!compiled) {
    const message = compiler.getErrorMessage() || "compiler returned failure\n";
    writeResult(workdir, {
      faustwasm_version: FAUSTWASM_VERSION,
      libfaust_version: libfaustVersion,
      library_tree_sha256: libraryTreeSha256,
      compile_ok: false,
      diagnostics: message.endsWith("\n") ? message : `${message}\n`,
      inputs: 0,
      outputs: 0,
      stimuli: [],
    });
    return;
  }
  const written = [];
  const stimulusMs = {};
  let inputCount = 0;
  let outputCount = 0;
  let buttonAddresses = [];
  try {
    for (const name of stimuli) {
      const started = performance.now();
      const processor = await generator.createOfflineProcessor(sampleRate, blockSize);
      inputCount = processor.getNumInputs();
      outputCount = processor.getNumOutputs();
      buttonAddresses = buttonsOf(processor);
      const mono = readMono(workdir, name, frames);
      const channels = renderOne(processor, mono, frames, blockSize, buttonAddresses, pressFirst);
      const fileName = `out-${name}.f32`;
      writeFileSync(join(workdir, fileName), planarBytes(channels));
      written.push(name);
      stimulusMs[name] = Math.max(0, Math.round(performance.now() - started));
      processor.destroy();
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "render failed";
    const termination = terminationFields(error);
    writeResult(workdir, {
      faustwasm_version: FAUSTWASM_VERSION,
      libfaust_version: libfaustVersion,
      library_tree_sha256: libraryTreeSha256,
      compile_ok: false,
      diagnostics: `internal: ${message.endsWith("\n") ? message : `${message}\n`}`,
      inputs: inputCount,
      outputs: outputCount,
      stimuli: written,
      runtime_stack_overflow: termination.runtime_stack_overflow,
      wasm_trap: termination.wasm_trap,
    });
    return;
  }
  writeResult(workdir, {
    faustwasm_version: FAUSTWASM_VERSION,
    libfaust_version: libfaustVersion,
    library_tree_sha256: libraryTreeSha256,
    toolchain: {
      faustwasm: FAUSTWASM_VERSION,
      node: process.version,
      node_flags: process.execArgv.filter(
        (flag) =>
          flag === "--disallow-code-generation-from-strings" ||
          flag === "--permission" ||
          flag.startsWith("--stack-size="),
      ),
      v8: process.versions.v8,
    },
    compile_ok: true,
    diagnostics: "",
    inputs: inputCount,
    outputs: outputCount,
    sample_rate: sampleRate,
    block_size: blockSize,
    frames,
    stimuli: written,
    buttons: buttonAddresses,
    stimulus_ms: stimulusMs,
  });
}

await main();
