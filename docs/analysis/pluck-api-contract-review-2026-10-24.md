# Render-duration preflight repair

Found a request-level gap in the local exact-pluck binding: RenderSpec.duration was forwarded without validation. Seven regression cases initially failed for True, a string, zero, negative, NaN, infinity, and a Python integer too large to convert to float. The tests mock RenderEngine, so malformed requests never reach the native renderer during diagnosis.

The candidate preflight now requires an explicit duration to be real, non-boolean, float-representable, finite and positive. Duration remains seconds regardless of time_unit. None retains automatic duration; a deliberate short crop remains accepted. No new arbitrary maximum render duration or listening decision was imposed.

After repair, seven unittest methods pass, including the existing 288 invalid-note entrypoint cases, changed-contract and tempo cases, and 14 duration rejections across render_spec/render_stems. Twelve actual render/export cases passed again at four rates, with exact seconds/beats agreement and retained release tails. This does not qualify arbitrarily large finite render allocation or concurrent mutation of global configuration.

Local proposal only. Independent musical review, rights/admission, independent evaluation families, and signed readiness artifacts remain pending. Historical review packets are unchanged; this directory binds the revised candidate wrapper and tests.
