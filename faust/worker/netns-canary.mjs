// Network-namespace canary shared by compile.mjs and render.mjs.
// The only interface may be `lo`, and a connect must fail. A failure
// writes `sandbox_canary_failed:` and exits 2. Python treats that
// marker as SandboxError and writes no receipt.

import { readFileSync } from "node:fs";
import { connect } from "node:net";

function failCanary(message) {
  process.stderr.write(`sandbox_canary_failed: ${message}\n`);
  process.exit(2);
}

function namespaceInterfaces() {
  let text;
  try {
    text = readFileSync("/proc/net/dev", "utf8");
  } catch {
    failCanary("network namespace interfaces could not be read");
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

export function assertNetworkIsolated() {
  const names = namespaceInterfaces();
  if (names.length !== 1 || names[0] !== "lo") {
    failCanary("network namespace has a non-loopback interface");
  }
  return new Promise((resolve) => {
    const socket = connect({ host: "1.1.1.1", port: 443 });
    const timer = setTimeout(() => {
      socket.destroy();
      failCanary("network connect did not fail inside the sandbox");
    }, 1000);
    socket.once("error", () => {
      clearTimeout(timer);
      socket.destroy();
      resolve();
    });
    socket.once("connect", () => {
      clearTimeout(timer);
      socket.destroy();
      failCanary("network connect succeeded inside the sandbox");
    });
  });
}
