# Bounded source Spark qualification

The exact bounded source `74f7aef25b5c12a0e077bb407ddf491ea920fa015e3a20eef2884aacdf2a56fe` passed the existing isolated Spark qualification harness. All40 static native cases pass; all24 per-sample live-control cases remain finite, including12 exact-silence controls. Four native/WASM comparisons each cover131072 frames with block64 controls spanning frequency440→8000→20Hz, gain0.5→0.25, and gate releases/retriggers. Maximum absolute difference is7.264316e-8 under the unchanged2e-6 absolute plus1e-5 relative tolerance.

Local capture verification checked exact source and runner identities, complete case coverage, output hashes, finite stereo shape, gain linearity and every native/WASM comparison sample. These checks use the same qualification workflow and do not constitute independent semantic review. Runtime pins and compiler/worker receipts remain in the WASM report. Existing worker isolation and resource limits were retained.

Network correction: earlier sandboxed SSH and npm attempts failed DNS resolution. The authorized network-enabled retry reached Spark and downloaded the pinned npm package. Those earlier failures did not establish that Spark was offline. The local package's SHA-512 integrity was verified, but qualification reported here used the existing Spark harness, not the newly downloaded local package. No production sandbox guard was removed.

The refreshed public Spark custody inventory contains14 scoped records and has unchanged SHA-256 `abe6d64818e92045320a4220dc5276e56371bef6dd0cffa73930233f5349bd25`. The T07 proposal remains unsigned/unfrozen; custody metadata still does not establish the required authenticated snapshot and trusted key binding. This refresh read only the previously scoped public metadata.

The new candidate contract combines fresh host and Spark evidence while leaving admission and independent semantic decisions pending. It is separate from the earlier source's semantic-review packet. Absolute tuning/musical acceptance, canonical rights/admission, independent evaluation families and authenticated signed readiness remain unresolved.

Local archive: `work/pluck-bounded-evidence.tar.gz`, SHA-256 `bc43bc3df0af60d8fd72e69ff49835537796fea4e0a927c94168a53629bf50e4`. It contains the source, generated native code, native/WASM captures, reports and qualification runners.
