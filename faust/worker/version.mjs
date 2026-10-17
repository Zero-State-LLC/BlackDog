// Print compiler.version() for the staged libfaust runtime and exit.
// Python runs this once per runtime hash, under the same sandbox as compile.mjs.

import { join } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

if (process.env.FAUSTCODER_SANDBOX !== "1" || process.permission === undefined) {
  process.stderr.write("refusing to run without the FaustCoder sandbox\n");
  process.exit(2);
}

const workdir = process.argv[2];
if (!workdir) {
  process.stderr.write("workdir argument is required\n");
  process.exit(2);
}

const entry = fileURLToPath(
  new URL("./node_modules/@grame/faustwasm/dist/esm/index.js", import.meta.url),
);
const faustwasm = await import(pathToFileURL(entry).href);
const runtimeJs = join(workdir, "runtime", "libfaust-wasm.js");
const faustModule = await faustwasm.instantiateFaustModuleFromFile(runtimeJs);
const compiler = new faustwasm.FaustCompiler(new faustwasm.LibFaust(faustModule));
const version = compiler.version();
if (typeof version !== "string" || version.length === 0) {
  process.stderr.write("libfaust version is empty\n");
  process.exit(2);
}
process.stdout.write(`${version}\n`);
