"""
Right now this only contains basic tests. Because the library depends heavily on
headspace, it makes it difficult to write automated tests.
"""

from pyheadspace.__main__ import round_off


def test_round_off_duration():
    assert round_off(1.1 * 60_000) == 1
    assert round_off(1.2 * 60_000) == 1
    assert round_off(1.9 * 60_000) == 1
    assert round_off(2 * 60_000) == 2
    assert round_off(2.5 * 60_000) == 2
    assert round_off(2.9 * 60_000) == 2
    assert round_off(3 * 60_000) == 3

    assert round_off(3.1 * 60_000) == 3
    assert round_off(3.9 * 60_000) == 3
    assert round_off(4 * 60_000) == 5
    assert round_off(5 * 60_000) == 5
    assert round_off(5.2 * 60_000) == 5
    assert round_off(6 * 60_000) == 5
    assert round_off(7 * 60_000) == 5
    assert round_off(10.2 * 60_000) == 10
    assert round_off(16 * 60_000) == 15
