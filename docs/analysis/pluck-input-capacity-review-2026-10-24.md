# Pluck input and capacity qualification

The diagnostic adapter binds the exact reset source `83cd856eaf46228903180244b2e5002e139f87decb39d2235a6df980d0b85ab8`, block size 64, eight voices, and `dynamic_voices=False`. Natural decay after note-off with clean retrigger remains a recommendation pending independent semantic review.

Input validation rejects fractional pitches instead of silently truncating them. Supported inputs are integer MIDI 16–119, integer velocity 1–127, finite nonnegative start, positive finite duration, and a finite end time. The rate must be one of 44.1, 48, 96 or 192 kHz. All notes are checked before allocating host objects, including malformed notes late in a batch. Twenty tests cover rejection without partial host mutation, source/rate binding, accepted pitch/velocity endpoints, and installed host policy. These tests establish preflight behavior, not audio qualification of every accepted pitch or time.

The pinned DawDreamer 0.9.0 host rendered twelve distinct short notes at each rate. Sixty hash-verified captures cover eight voices, an exact repeat, a sixteen-voice reference, and twelve solos per rate. Eight-voice repeats are byte-identical. Sixteen-voice mixes equal the solo sums exactly. Eight-versus-sixteen maximum absolute differences range from 0.7621 to 0.7863: released tails are cut under exhaustion. This is a measured capacity limitation; no perceptual acceptance or transparent stealing is claimed. Increasing the reference voice count does not change the proposed eight-voice policy.

The evidence archive is `work/pluck-exhaustion-evidence.tar.gz` in the recovery workspace; its SHA-256 is recorded in the JSON receipt and contract. The archived runner uses recovery-workspace paths and requires the pinned host environment described in the reset-host contract. Capture verification is performed within the same qualification workflow and is not an independent semantic decision.

The Designing Sound provenance issue remains open with zero comments at this check: https://github.com/materializepath/designing-sound-experiments/issues/1 . No teacher provenance has been inferred from silence.

No canonical pair was admitted and no evaluation family was declared independent. Longer tails, rapid retrigger histories, epoch-counter lifetime, upstream integration, independent semantic decisions, family independence and authenticated signed readiness artifacts remain open.

## Sample-offset boundary correction

Finite seconds alone were insufficient: DawDreamer 0.9.0 converts `start*rate` and `start*rate+duration*rate` to signed integer sample offsets. The adapter now rejects overflow and durations whose on/off offsets collapse into the same sample before allocating the host. The check uses the host's operation order. Twenty additional rate/boundary tests pass (40 adapter tests total), including representable upper boundaries and one-sample durations. All 60 accepted-schedule captures were rerendered with the changed adapter and match the prior bytes exactly. This does not claim long-duration audio validation.

Source evidence: https://github.com/DBraun/DawDreamer/blob/v0.9.0/Source/FaustProcessor.cpp#L1249-L1284 . Prior capture receipts retain their original adapter hashes; the new receipt binds the corrected adapter.
