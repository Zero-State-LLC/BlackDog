# One-shot iterable input repair

A new regression reproduced that preflight accepted and consumed a one-shot note iterator, leaving the later rendering pass without those notes. The exact candidate wrapper now requires list or tuple for spec.tracks and track.notes. This rejects generators before host allocation in both render_spec and render_stems; documented list-based input and reusable tuples remain supported. It does not change generic Shipwright defaults.

Eight unittest methods pass, including four one-shot iterable rejection combinations. The four-rate dry multitrack/stem regression passes again with the revised wrapper. DSP bytes and the original musical-review packet are unchanged. This revises the local API proposal and supersedes its wrapper in review bundle v2; v3 includes the revised wrapper/tests and report. No approval or admission is implied.
