"""Generate specialized diagnostic fixtures; never an admission decision.

The caller must execute at Config.sample_rate. This is offline specialization,
not a dynamically reconfigurable replacement for the public analyzer API.
The closure argument is the previously captured, rights-tracked spectral source.
"""
from dataclasses import dataclass, asdict
import hashlib
import math
import struct


@dataclass(frozen=True)
class Config:
    sample_rate: int
    top_hz: float
    bands: int = 3
    bands_per_octave: float = 3
    tau: float = .01
    offset_db: float = 0

    def validate(self):
        if type(self.sample_rate) is not int or not 8000 <= self.sample_rate <= 192000:
            raise ValueError('sample_rate must be an integer in [8000,192000]')
        if type(self.bands) is not int or not 2 <= self.bands <= 8:
            raise ValueError('bands must be an integer in [2,8]')
        if not all(math.isfinite(x) for x in
                   (self.top_hz, self.bands_per_octave, self.tau, self.offset_db)):
            raise ValueError('parameters must be finite')
        if not 0 < self.top_hz < .499 * self.sample_rate:
            raise ValueError('top_hz must be positive and below .499*sample_rate')
        if self.bands_per_octave <= 0 or self.tau <= 0:
            raise ValueError('bands_per_octave and tau must be positive')
        if self.cutoffs[-1] < 1:
            raise ValueError('lowest cutoff must be at least 1 Hz')

    @property
    def cutoffs(self):
        return [self.top_hz * 2 ** (-i / self.bands_per_octave)
                for i in range(self.bands - 1)]


def split32(value):
    hi = struct.unpack('<f', struct.pack('<f', value))[0]
    lo = struct.unpack('<f', struct.pack('<f', value - hi))[0]
    return hi, lo


# Numerical prototype values from the already rights-tracked 6e fixture.
# This generator does not grant rights to those definitions or the input closure.
PROTOTYPE = (
    (.000099999997055, .000433227200555, .782413046821645, .245291508706160),
    (1, 7.621731298870603, .512478641889141, .689621364484675),
    (1, 53.536152954556727, .168404871113589, 1.069358407707312),
)


def coefficient_parts(value):
    hi, lo = split32(value)
    rounding = lambda x: split32(x)[0]
    scaled = rounding(4097 * hi)
    split_hi = rounding(scaled - rounding(scaled - hi))
    split_lo = rounding(hi - split_hi)
    return hi, lo, split_hi, split_lo


def specialize_arithmetic(arithmetic):
    start = arithmetic.index('biquad(')
    body = arithmetic[start:].replace('mul(', 'mulconst(')
    for name in ('b0', 'b1', 'b2', 'a1', 'a2'):
        body = body.replace(f'{name}h,{name}l', f'{name}h,{name}l,{name}sh,{name}sl')
    constmul = """
mulconst(a,b,ah,al,c,d) = (r(a*c),e) : renorm with {
 cc=r(4097*c);ch=r(cc-r(cc-c));cl=r(c-ch);p=r(a*c);
 e=r(r(r(r(r(r(ah*ch)-p)+r(ah*cl))+r(al*ch))+r(al*cl))+r(r(a*d)+r(b*c)));
};
"""
    return arithmetic[:start] + constmul + body


def filter_code(rate, cutoff, high):
    calls = []
    for b2, b0, a1, a0 in PROTOTYPE:
        if high:
            b2, b0, a1, a0 = b0 / a0, b2 / a0, a1 / a0, 1 / a0
        c = 1 / math.tan(math.pi * cutoff / rate)
        d = a0 + a1 * c + c * c
        coeffs = ((b0 + b2*c*c)/d, 2*(b0-b2*c*c)/d,
                  (b0+b2*c*c)/d, -2*(a0-c*c)/d, -(a0-a1*c+c*c)/d)
        args = ','.join(f'{part:.17e}' for x in coeffs for part in coefficient_parts(x))
        calls.append(f'biquad({args})')
    return ':'.join(calls)


def build(closure, config, arithmetic):
    config.validate()
    if closure.count('an = environment {') != 1:
        raise ValueError('expected exactly one analyzer environment')
    # Keep the complete tracked dependency closure rather than dropping dead helpers.
    tail = closure[closure.index('an = environment {'):]
    start = tail.index('mth_octave_analyzer6e_tpt_df(L,M,ftop,N) =')
    end = tail.index('mth_octave_spectral_level6e(', start)
    ds = ['ds = environment {', specialize_arithmetic(arithmetic)]
    for i, fc in enumerate(config.cutoffs):
        for high in (False, True):
            ds.append(f'{"hp" if high else "lp"}{i} = {filter_code(config.sample_rate, fc, high)};')
    ds.append('};')
    branches = []
    for i in range(config.bands):
        stages = ([f'ds.hp{i}'] if i < config.bands-1 else [])
        stages += [f'ds.lp{j}' for j in range(i)]
        branches.append('_,0 : ' + ' : '.join(stages) + ' : +')
    analyzer = 'mth_octave_analyzer6e_tpt_df(L,M,ftop,N) = _ <: ' + ','.join(f'({x})' for x in branches) + ';\n'
    tail = tail[:start] + analyzer + tail[end:]
    tail = tail.rsplit('process =', 1)[0]
    source = '\n'.join(ds) + '\n' + tail + (
        f'process = an.mth_octave_spectral_level_default('
        f'{config.bands_per_octave:.17g},{config.top_hz:.17g},'
        f'{config.bands},{config.tau:.17g},{config.offset_db:.17g});\n')
    return dict(source=source, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                closure_sha256=hashlib.sha256(source.rsplit('process =', 1)[0].encode()).hexdigest(),
                required_sample_rate=config.sample_rate, parameters=asdict(config),
                cutoffs=config.cutoffs, admission='NOT_GRANTED')


def require_runtime_rate(fixture, sample_rate):
    """Fail closed before executing coefficients specialized for a different rate."""
    if type(sample_rate) is not int or sample_rate != fixture['required_sample_rate']:
        raise ValueError('runtime sample rate does not match specialized coefficients')


def main():
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--closure', type=Path, required=True)
    parser.add_argument('--arithmetic', type=Path, required=True)
    parser.add_argument('--sample-rate', type=int, required=True)
    parser.add_argument('--top-hz', type=float, required=True)
    parser.add_argument('--bands', type=int, default=3)
    parser.add_argument('--bands-per-octave', type=float, default=3)
    parser.add_argument('--tau', type=float, default=.01)
    parser.add_argument('--offset-db', type=float, default=0)
    args = parser.parse_args()
    config = Config(args.sample_rate, args.top_hz, args.bands,
                    args.bands_per_octave, args.tau, args.offset_db)
    print(json.dumps(build(args.closure.read_text(), config,
                           args.arithmetic.read_text()), indent=2))


if __name__ == '__main__':
    main()
