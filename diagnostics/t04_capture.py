"""Diagnostic only: retain the normal sandboxed DSP-bank render artifacts."""
import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

import faustcoder.signal as s
from faustcoder.signal_suite import DSP_BANK, nonlinear_suite_profile, wire_reference

out = Path('evidence').resolve()
out.mkdir(exist_ok=True)
worker = s.worker_directory()
target = worker / 'render-t04-capture-local.mjs'
assert not target.exists()
source = (worker / 'render.mjs').read_text()
needle = '  const written = [];'
assert source.count(needle) == 1
source = source.replace(needle,
    '  writeFileSync(join(workdir, "compiled.wasm"), generator.factory.code);\n'
    '  writeFileSync(join(workdir, "factory.json"), generator.factory.json);\n' + needle)
target.write_text(source)
(out / 'render-capture.mjs').write_text(source)
original_command = s.node_command
original_read = s._read_outputs

def command(script, *args, **kwargs):
    return original_command(target if script.name == 'render.mjs' else script, *args, **kwargs)

s.node_command = command
profile = nonlinear_suite_profile()
reference = wire_reference(profile)
summary = {'arch': platform.machine(), 'commit': subprocess.check_output(
    ['git', 'rev-parse', 'HEAD'], text=True).strip(), 'programs': {}}
goldens = json.loads(Path('tests/fixtures/signal/nonlinear-x86-goldens.json').read_text())
try:
    for name, dsp in DSP_BANK.items():
        destination = out / name
        destination.mkdir()
        (destination / 'source.dsp').write_text(dsp)
        def capture(workdir, *args, **kwargs):
            samples = original_read(workdir, *args, **kwargs)
            for item in Path(workdir).iterdir():
                if item.is_file():
                    shutil.copy2(item, destination / item.name)
            shutil.copytree(Path(workdir) / 'inputs', destination / 'inputs')
            return samples
        s._read_outputs = capture
        result = s.run_signal(dsp, profile, reference, options=s.PINNED_COMPILE_FLAGS)
        (destination / 'receipt.json').write_text(json.dumps(result.receipt, indent=2) + '\n')
        assert (destination / 'compiled.wasm').read_bytes().startswith(b'\x00asm')
        hashes = {k: v['sample_sha256'] for k, v in result.receipt['metrics']['renders'].items()}
        summary['programs'][name] = {'hashes': hashes, 'golden_matches': sum(
            h == goldens['programs'][name]['sample_sha256'][k] for k, h in hashes.items())}
        print(name, summary['programs'][name]['golden_matches'], flush=True)
finally:
    target.unlink()
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    files = sorted(p for p in out.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
    (out / 'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()
        + '  ' + str(p.relative_to(out)) + '\n' for p in files))
subprocess.run(['git', 'diff', '--exit-code', 'HEAD'], check=True)
