// Original FaustCoder fixture. Not from the Faust distribution.
// Adds 0.25 DC once the sample counter passes 3000. Not an impulse-test source.
process = _ + ((+(1) ~ _) > 3000) * 0.25;
