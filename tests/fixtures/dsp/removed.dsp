// Not from the Faust distribution.
// tonestacks.lib at 2edec0537f53 no longer exports fi.
ts = library("tonestacks.lib");
process = ts.fi.lowpass(1, 1000);
