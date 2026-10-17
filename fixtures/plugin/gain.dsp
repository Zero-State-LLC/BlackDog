declare name "FCGain"; declare vendor "ZeroState"; declare version "0.1";
import("stdfaust.lib");
g = hslider("gain[unit:dB]",0,-60,12,0.1) : ba.db2linear : si.smoo;
process = _*g, _*g;
