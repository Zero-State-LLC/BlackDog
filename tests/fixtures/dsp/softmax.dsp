// Not from the Faust distribution.
import("stdfaust.lib");
process = (-0.1, 0.2, 0.3, -0.2) : si.softmax(4, 0.5);
