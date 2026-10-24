// Optional diagnostic boundary. Legacy renderOne remains byte-for-byte unchanged.
const INPUTS = new Set(['sine', 'noise', 'impulse', 'multitone', 'alternating']);
export function validateDiagnostic(spec, descriptors, frames, blockSize, inputs, pressFirst) {
  if (!spec || spec.version !== 1 || !/^[A-Za-z0-9_-]{1,80}$/.test(spec.case_id) || !Array.isArray(spec.controls)) throw Error('invalid diagnostic case');
  if (inputs === 0 && spec.input_stimuli === null) throw Error('zero-input DSP requires explicit empty routing');
  if (spec.input_stimuli !== null && (!Array.isArray(spec.input_stimuli) || spec.input_stimuli.length !== inputs || spec.input_stimuli.some(n => !INPUTS.has(n)))) throw Error('input count or stimulus mismatch');
  const writable = new Map();
  const pending = [...descriptors];
  while (pending.length) {
    const item = pending.shift();
    if (Array.isArray(item.items)) pending.push(...item.items);
    if (['button','checkbox','hslider','vslider','nentry'].includes(item.type)) {
      if (writable.has(item.address)) throw Error('duplicate writable descriptor');
      writable.set(item.address, item);
    }
  }
  let previous;
  for (const event of spec.controls) {
    if (!Number.isInteger(event.block) || event.block < 0 || event.block >= frames / blockSize || typeof event.address !== 'string' || typeof event.value !== 'number' || !Number.isFinite(event.value)) throw Error('invalid control event');
    if (previous && (event.block < previous.block || (event.block === previous.block && event.address <= previous.address))) throw Error('controls must be sorted and unique');
    previous = event;
    const item = writable.get(event.address);
    if (!item) throw Error('unknown writable control');
    if (item.type === 'button' && pressFirst) throw Error('explicit button conflicts with automatic button policy');
    const [low, high, step] = ['button','checkbox'].includes(item.type) ? [0,1,1] : [item.min,item.max,item.step];
    if (![low,high,step].every(v => typeof v === 'number' && Number.isFinite(v)) || high < low || step < 0) throw Error('invalid control descriptor');
    if (event.value < low || event.value > high) throw Error('control out of range');
    if (step && Math.abs((event.value-low)/step - Math.round((event.value-low)/step)) > 1e-7) throw Error('control off step grid');
  }
}

export function renderDiagnostic(proc, channelInputs, frames, blockSize, buttons, pressFirst, events) {
  if (channelInputs.length !== proc.getNumInputs() || channelInputs.some(c => c.length !== frames || !c.every(Number.isFinite))) throw Error('invalid input samples');
  const outputs = proc.getNumOutputs();
  if (outputs < 1) throw Error('renderer produced no outputs');
  const channels = Array.from({length: outputs}, () => new Float32Array(frames));
  const explicit = new Set(events.map(e => e.address));
  const applied = [];
  proc.start();
  try {
    let next = 0;
    for (let offset = 0; offset < frames; offset += blockSize) {
      for (const address of buttons) if (!explicit.has(address)) proc.setParamValue(address, pressFirst && offset === 0 ? 1 : 0);
      while (next < events.length && events[next].block === offset / blockSize) {
        const e = events[next++];
        proc.setParamValue(e.address, e.value);
        applied.push({...e});
      }
      const ins = channelInputs.map(c => c.subarray(offset, offset + blockSize));
      const outs = Array.from({length: outputs}, () => new Float32Array(blockSize));
      if (!proc.compute(ins, outs)) throw Error('compute returned false');
      outs.forEach((channel, i) => channels[i].set(channel, offset));
    }
  } finally { proc.stop(); }
  return {channels, applied};
}
