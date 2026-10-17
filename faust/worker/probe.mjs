// Sandbox probes. These are not the compiler. Python runs them with the same
// isolation flags as compile.mjs and checks the one-line stdout token.

import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import net from "node:net";

if (process.env.FAUSTCODER_SANDBOX !== "1" || process.permission === undefined) {
  process.stderr.write("refusing to run without the FaustCoder sandbox\n");
  process.exit(2);
}

const mode = process.argv[2];
const workdir = process.argv[3] || "";

function token(text) {
  process.stdout.write(`${text}\n`);
}

if (mode === "network") {
  const socket = net.connect({ host: "1.1.1.1", port: 443 });
  socket.on("connect", () => {
    token("connected");
    process.exit(2);
  });
  socket.on("error", () => {
    token("blocked");
    process.exit(0);
  });
  setTimeout(() => {
    token("no-connect");
    process.exit(0);
  }, 500);
} else if (mode === "eval") {
  try {
    eval("1");
    token("eval-ok");
    process.exit(2);
  } catch {
    token("eval-blocked");
    process.exit(0);
  }
} else if (mode === "memory") {
  const chunks = [];
  for (let index = 0; index < 20; index += 1) {
    chunks.push(Buffer.alloc(8 * 1024 * 1024, 1));
  }
  setInterval(() => {
    chunks[0][0] = 1;
  }, 1000);
} else if (mode === "output") {
  writeFileSync(join(workdir, "big.bin"), Buffer.alloc(1024 * 1024, 1));
  token("wrote");
} else if (mode === "escape") {
  let readBlocked = false;
  try {
    readFileSync("/etc/passwd");
  } catch {
    readBlocked = true;
  }
  let writeBlocked = false;
  try {
    writeFileSync("/tmp/faustcoder-t03-escape", "nope");
  } catch {
    writeBlocked = true;
  }
  token(readBlocked && writeBlocked ? "fs-blocked" : "fs-open");
} else if (mode === "env") {
  const keys = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NODE_OPTIONS", "npm_config_registry"];
  const present = keys.filter((key) => process.env[key]);
  token(present.length === 0 ? "env-clean" : `env-dirty ${present.join(",")}`);
} else {
  process.stderr.write("unknown probe\n");
  process.exit(2);
}
