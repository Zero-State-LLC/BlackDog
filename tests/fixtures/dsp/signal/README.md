# Signal harness fixtures

These Faust sources exercise the T04 signal harness. They are original
FaustCoder fixtures. They are not copies of Faust `tests/impulse-tests`,
and they are not the development suite or the sealed holdout.

`needs_stdfaust.dsp` imports `stdfaust.lib`. The harness does not render
it. Pinned faustlibraries staging is T03b.

Every other file is library-free. A comment in each file says it is not
from the Faust distribution.
