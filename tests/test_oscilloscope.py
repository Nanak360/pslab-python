"""Tests for PSL.oscilloscope.

When integration testing, the PSLab's analog output is used to generate a
signal which is sampled by the oscilloscope. Before running the integration
tests, connect SI1->CH1->CH2->CH3.
"""

import numpy as np
import pytest

from PSL import oscilloscope
from PSL import packet_handler
from PSL import sciencelab

FREQUENCY = 1000
MICROSECONDS = 1e-6
ABSTOL = 4 * (16.5 - (-16.5)) / (2 ** 10 - 1)  # Four times lowest CH1/CH2 resolution.


@pytest.fixture
def scope(handler):
    """Return an Oscilloscope instance.

    In integration test mode, this function also enables the analog output.
    """
    if not isinstance(handler, packet_handler.MockHandler):
        psl = sciencelab.connect()
        psl.H.disconnect()
        psl.H = handler
        psl.set_sine1(FREQUENCY)
        handler._logging = True
    return oscilloscope.Oscilloscope(handler)


def count_zero_crossings(x, y):
    sample_rate = (np.diff(x)[0] * MICROSECONDS) ** -1
    samples_per_period = sample_rate / FREQUENCY
    zero_crossings = np.where(np.diff(np.sign(y)))[0]
    real_crossings = np.where(np.diff(zero_crossings) > samples_per_period * 0.01)
    real_crossings = np.append(real_crossings, True)

    if len(real_crossings) % 1:
        if y[0] * y[-1] <= 0:
            return len(real_crossings) + 1

    return len(real_crossings)


def verify_periods(x, y, channel, periods=1):
    zero_crossings = count_zero_crossings(x, y)
    assert zero_crossings == 2 * periods
    assert y[0] == pytest.approx(y[-1], abs=ABSTOL)


def test_capture_one_12bit(scope):
    _, y = scope.capture(channels=1, samples=1000, timegap=1)
    y.sort()
    resolution = min(np.diff(y)[np.diff(y) > 0])
    expected = (16.5 - (-16.5)) / (2 ** 12 - 1)
    assert resolution == pytest.approx(expected)


def test_capture_one_high_speed(scope):
    x, y = scope.capture(channels=1, samples=2000, timegap=0.5)
    verify_periods(x, y, scope._channels["CH1"])


def test_capture_one_trigger(scope):
    scope.trigger_enabled = True
    _, y = scope.capture(channels=1, samples=1, timegap=1)
    assert y[0] == pytest.approx(0, abs=ABSTOL)


def test_capture_two(scope):
    x, y1, y2 = scope.capture(channels=2, samples=500, timegap=2)
    verify_periods(x, y1, scope._channels["CH1"])
    verify_periods(x, y2, scope._channels["CH2"])


def test_capture_four(scope):
    x, y1, y2, y3, _ = scope.capture(channels=4, samples=500, timegap=2)
    verify_periods(x, y1, scope._channels["CH1"])
    verify_periods(x, y2, scope._channels["CH2"])
    verify_periods(x, y3, scope._channels["CH3"])


def test_capture_invalid_channel_one(scope):
    scope.channel_one_map = "BAD"
    with pytest.raises(ValueError):
        scope.capture(channels=1, samples=200, timegap=2)


def test_capture_timegap_too_small(scope):
    with pytest.raises(ValueError):
        scope.capture(channels=1, samples=200, timegap=0.2)


def test_capture_too_many_channels(scope):
    with pytest.raises(ValueError):
        scope.capture(channels=5, samples=200, timegap=2)


def test_capture_too_many_samples(scope):
    with pytest.raises(ValueError):
        scope.capture(channels=4, samples=3000, timegap=2)


def test_configure_trigger(scope):
    scope.channel_one_map = "CH3"
    scope.configure_trigger(channel="CH3", voltage=1.5)
    _, y = scope.capture(channels=1, samples=1, timegap=1)
    assert y[0] == pytest.approx(1.5, abs=ABSTOL)


def test_configure_trigger_on_unmapped(scope):
    with pytest.raises(TypeError):
        scope.configure_trigger(channel="AN8", voltage=1.5)


def test_configure_trigger_on_remapped_ch1(scope):
    scope.channel_one_map = "CAP"
    with pytest.raises(TypeError):
        scope.configure_trigger(channel="CH1", voltage=1.5)


def test_select_range(scope):
    scope.select_range("CH1", 1.5)
    _, y = scope.capture(channels=1, samples=1000, timegap=1)
    assert 1.5 <= max(y) <= 1.65


def test_select_range_invalid(scope):
    with pytest.raises(ValueError):
        scope.select_range("CH1", 15)
