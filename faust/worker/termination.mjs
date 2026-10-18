// Structured termination for a JS exception the worker caught.
// A signal death never reaches this module: the process is already gone,
// and Python records the signal number from the wait status.
// These shapes are line-start and case-sensitive. They are the runtime's
// own exception, not harness prose.

const WASM_TRAPS = [
  "unreachable",
  "memory access out of bounds",
  "indirect call type mismatch",
  "indirect call signature mismatch",
  "table index is out of bounds",
  "call stack exhausted",
  "null function",
  "indirect call to null",
  "uninitialized element",
];

function firstLine(error) {
  const message = error instanceof Error ? error.message : "";
  const line = message.split("\n")[0];
  return line;
}

function matchesKind(line, kind) {
  return line === kind || line.startsWith(`${kind} `) || line.startsWith(`${kind}:`);
}

export function terminationFields(error) {
  const name = error instanceof Error ? error.name : "";
  const line = firstLine(error);
  const runtimeStack =
    name === "RangeError" || line.startsWith("Maximum call stack size exceeded");
  let wasmTrap = null;
  if (name === "RuntimeError") {
    for (const kind of WASM_TRAPS) {
      if (matchesKind(line, kind)) {
        wasmTrap = kind;
        break;
      }
    }
  }
  return {
    runtime_stack_overflow: runtimeStack,
    wasm_trap: wasmTrap,
  };
}
