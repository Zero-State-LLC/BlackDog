# Notice pin reconciliation

CI at 9d91feb reported 3 failures and 56 setup errors from a stale notice digest; 1357 tests passed. Commits 20305c4 and 25f1aca added seven Ribbon and Shipwright dependency notices. The prior 2080 entries and every other top-level field are unchanged. The validator now pins the exact 2087-entry manifest: `sha256:1a6d5c0ea41d2e6ccc14dd2127ca8a3e92e4ef06ad66bf857b8bd729a7d4897a`. Digest enforcement remains enabled. This reconciles notice bookkeeping and grants no candidate admission, independent review, or signed readiness.

Local targeted replay: 107 of 110 tests passed, with no manifest-digest failures. Two fixtures collide on the case-insensitive macOS filesystem (Birds.dsp and birds.dsp); one requires the absent pinned instruments.lib checkout. Linux CI is required to verify these three cases. Fresh v3 Shipwright review-bundle reproduction passed all 12 API tests.
