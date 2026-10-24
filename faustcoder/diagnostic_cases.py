"""Opt-in diagnostic cases (ADR-0008); never reward-profile admission."""
from __future__ import annotations

from dataclasses import dataclass, replace
import copy
import hashlib
import math
import re
from typing import Any, Sequence

from faustcoder.canonical import content_digest_for

VERSION = 1
INPUT_NAMES = frozenset({"sine", "noise", "impulse", "multitone", "alternating"})


@dataclass(frozen=True)
class ControlEvent:
    block: int
    address: str
    value: float

    def __post_init__(self):
        if type(self.block) is not int or self.block < 0:
            raise ValueError("control block must be a nonnegative integer")
        if not isinstance(self.address, str) or not self.address.startswith("/"):
            raise ValueError("control address must be absolute")
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)) or not math.isfinite(self.value):
            raise ValueError("control value must be finite")
        object.__setattr__(self, "value", float(self.value))

    def payload(self):
        # Float hex preserves exact values without lossy nano quantization.
        return {"block": self.block, "address": self.address, "value_hex": self.value.hex()}


@dataclass(frozen=True)
class DiagnosticCase:
    case_id: str
    controls: tuple[ControlEvent, ...] = ()
    input_stimuli: tuple[str, ...] | None = None
    zero_companion: str | None = None

    def __post_init__(self):
        for value in (self.case_id, self.zero_companion):
            if value is not None and (not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value)):
                raise ValueError("case IDs must be short safe identifiers")
        if self.case_id is None or self.zero_companion == self.case_id:
            raise ValueError("expected-zero companion must be distinct")
        object.__setattr__(self, "controls", tuple(self.controls))
        if any(not isinstance(e, ControlEvent) for e in self.controls):
            raise ValueError("controls must be ControlEvent records")
        identities = [(e.block, e.address) for e in self.controls]
        if identities != sorted(identities) or len(set(identities)) != len(identities):
            raise ValueError("controls must be sorted and unique by block/address")
        if self.input_stimuli is not None:
            object.__setattr__(self, "input_stimuli", tuple(self.input_stimuli))
            if any(n not in INPUT_NAMES for n in self.input_stimuli):
                raise ValueError("unknown input stimulus")

    def validate_profile(self, profile):
        if type(profile.block_size) is not int or profile.block_size < 1 or type(profile.frames) is not int:
            raise ValueError("diagnostic frames and block size must be positive integers")
        if any(e.block >= profile.frames // profile.block_size for e in self.controls):
            raise ValueError("control block outside render")
        if profile.absolute_tolerance != 2e-6 or profile.relative_tolerance != 1e-5:
            raise ValueError("diagnostic cases retain the pinned comparison tolerances")
        if not profile.reject_nonfinite or not profile.reject_silence or not profile.require_reference:
            raise ValueError("diagnostic cases require finite/reference/silence checks")
        if profile.suite is not None:
            raise ValueError("diagnostic cases cannot extend a named suite")

    def payload(self):
        return {"version": VERSION, "case_id": self.case_id,
                "controls": [e.payload() for e in self.controls],
                "input_stimuli": None if self.input_stimuli is None else list(self.input_stimuli),
                "zero_companion": self.zero_companion}

    def worker_payload(self):
        return {**self.payload(), "controls": [
            {"block": e.block, "address": e.address, "value": e.value} for e in self.controls]}


def input_buffers(profile):
    """Channel order is semantic. New generators use fixed float32 definitions."""
    from faustcoder.signal import f32, sine_samples, noise_samples, impulse_samples
    case = profile.diagnostic_case
    result = []
    for name in case.input_stimuli or ():
        if name == "sine":
            values = sine_samples(profile.frames, profile.sample_rate, profile.sine_hz, profile.sine_amplitude)
        elif name == "noise":
            values = noise_samples(profile.frames, profile.seed, profile.noise_amplitude)
        elif name == "impulse":
            values = impulse_samples(profile.frames, profile.impulse_amplitude)
        elif name == "alternating":
            values = [f32(0.25 if i % 2 == 0 else -0.25) for i in range(profile.frames)]
        else:
            a = sine_samples(profile.frames, profile.sample_rate, 431, 0.125)
            b = sine_samples(profile.frames, profile.sample_rate, 997, 0.125)
            values = [f32(x + y) for x, y in zip(a, b, strict=True)]
        if not all(math.isfinite(v) for v in values):
            raise ValueError("nonfinite input samples")
        result.append(values)
    return result


def validate_controls(case, descriptors, frames, block_size, press_first):
    """Mirror the compiled-boundary worker checks; bargraphs are not writable."""
    writable = {}
    pending = list(descriptors)
    while pending:
        item = pending.pop(0)
        pending.extend(item.get("items", []))
        if item.get("type") in {"button", "checkbox", "hslider", "vslider", "nentry"}:
            address = item.get("address")
            if address in writable:
                raise ValueError("duplicate writable descriptor")
            writable[address] = item
    for event in case.controls:
        if event.block >= frames // block_size or event.address not in writable:
            raise ValueError("unknown control or block outside render")
        item = writable[event.address]
        toggle = item["type"] in {"button", "checkbox"}
        if item["type"] == "button" and press_first:
            raise ValueError("explicit button conflicts with automatic button policy")
        low, high, step = (0, 1, 1) if toggle else (item.get("min"), item.get("max"), item.get("step"))
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (low, high, step)) or step < 0 or high < low:
            raise ValueError("invalid control descriptor")
        if not low <= event.value <= high:
            raise ValueError("control out of range")
        if step and abs((event.value-low)/step-round((event.value-low)/step)) > 1e-7:
            raise ValueError("control off step grid")


def validate_worker_result(profile, body, buffers):
    from faustcoder.signal import _f32_bytes
    case = profile.diagnostic_case
    info = body.get("diagnostic_case")
    if not isinstance(info, dict) or info.get("spec") != case.worker_payload():
        raise ValueError("worker diagnostic case mismatch")
    descriptors = info.get("descriptors")
    if not isinstance(descriptors, list):
        raise ValueError("worker descriptors missing")
    validate_controls(case, descriptors, profile.frames, profile.block_size, profile.press_buttons_first_block)
    expected_events = case.worker_payload()["controls"]
    if info.get("applied_controls") != {n: expected_events for n in profile.stimuli}:
        raise ValueError("worker applied controls mismatch")
    if case.input_stimuli is not None and len(case.input_stimuli) != body["inputs"]:
        raise ValueError("input count mismatch")
    # Descriptor numbers are serialized as hex strings for canonical integer-only receipts.
    def canonical_descriptor(value):
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("nonfinite descriptor")
            return {"float_hex": value.hex()}
        if isinstance(value, list):
            return [canonical_descriptor(v) for v in value]
        if isinstance(value, dict):
            return {k: canonical_descriptor(v) for k, v in value.items()}
        return value
    return {"spec": case.payload(), "descriptor_digest": content_digest_for(canonical_descriptor(descriptors)),
            "applied_controls": {n: [e.payload() for e in case.controls] for n in profile.stimuli},
            "stimulus_sha256": {n: hashlib.sha256(_f32_bytes(v)).hexdigest() for n, v in sorted(buffers.items())},
            "input_definitions": {"multitone": {"frequencies_hz": [431, 997], "amplitudes_hex": [float(.125).hex()]*2, "phase": 0},
                                  "alternating": {"amplitude_hex": float(.25).hex(), "first_sign": 1}},
            "companion_receipt_digest": None}


def run_diagnostic_cases(source: str, profiles: Sequence[Any], references: Sequence[Any], *, options=(), limits=None):
    """Execute the entire batch ourselves; never accept caller-supplied pass receipts."""
    from faustcoder.signal import run_signal, reproducible_signal_digest
    if len(profiles) != len(references) or not profiles:
        raise ValueError("one explicit reference is required per case")
    indexed = {}
    for p, ref in zip(profiles, references, strict=True):
        case = p.diagnostic_case
        if not isinstance(case, DiagnosticCase) or case.case_id in indexed:
            raise ValueError("unique diagnostic case IDs required")
        if ref is None or ref.frames != p.frames:
            raise ValueError("explicit full-length reference required")
        indexed[case.case_id] = (p, ref)
    for p, ref in indexed.values():
        companion = p.diagnostic_case.zero_companion
        if companion is not None:
            if companion not in indexed or indexed[companion][0].diagnostic_case.zero_companion is not None:
                raise ValueError("missing, cyclic or expected-zero companion")
            other, other_ref = indexed[companion]
            if any(math.sqrt(math.fsum(float(v)**2 for ch in channels for v in ch)
                             / sum(len(ch) for ch in channels)) < other.silence_rms
                   for channels in other_ref.samples.values()):
                raise ValueError("companion requires a non-silent reference for every stimulus")
            if (p.sample_rate, p.block_size, p.seed, p.frames) != (other.sample_rate, other.block_size, other.seed, other.frames):
                raise ValueError("companion render setup mismatch")
            if any(float(v) != 0 for chs in ref.samples.values() for ch in chs for v in ch):
                raise ValueError("expected-zero reference must be all zero")
    runs = {name: run_signal(source, p, ref, options=options, limits=limits) for name, (p, ref) in indexed.items()}
    for name, (p, _) in indexed.items():
        companion = p.diagnostic_case.zero_companion
        if companion is None:
            continue
        run, other = runs[name], runs[companion]
        receipt = copy.deepcopy(run.receipt)
        ok = (other.receipt["passed"] and run.compilation.reproducible_digest == other.compilation.reproducible_digest
              and run.receipt["harness_digest"] == other.receipt["harness_digest"]
              and all(v.get("finite") and v.get("silence") is False for v in other.receipt["metrics"]["renders"].values()))
        failures = list(run.failures)
        if ok:
            allowed = {"diagnostic:companion_pending", *(f"{n}:silence" for n in p.stimuli)}
            failures = [f for f in failures if f not in allowed]
        else:
            failures.append("diagnostic:companion_failed")
        receipt["metrics"]["diagnostic_case"]["companion_receipt_digest"] = other.reproducible_digest
        receipt["metrics"]["failures"] = sorted(set(failures))
        receipt["passed"] = not failures
        runs[name] = replace(run, receipt=receipt, failures=tuple(receipt["metrics"]["failures"]),
                             reproducible_digest=reproducible_signal_digest(receipt))
    return tuple(runs[p.diagnostic_case.case_id] for p in profiles)
