"""
Test suites for A/M-i

Each test module has a "success" variable recording the overall outcome
for the test suite

Check vd[i] for the ith simulation test to see final state of simulation

For I/O-related tests, also check stdin[i] or stdout[i] for
tests._tools.IOSimulator containers storing I/O for each test
"""

import tests.arith
import tests.comp
import tests.branch
import tests.phi
import tests.io
import tests.debug
