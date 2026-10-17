// Original FaustCoder fixture: deep recursion. Not from the Faust distribution.
f(n) = f(n - 1) + 1;
process = f(10000000);
