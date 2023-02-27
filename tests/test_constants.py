from idpmodem.constants import WakeupPeriod, PowerMode, InmarsatSatellites


def test_wakeup_is_valid():
    for i in range(0, 11):
        assert WakeupPeriod.is_valid(i)
    assert not WakeupPeriod.is_valid(12)


def test_closest_satellite():
    assert InmarsatSatellites.closest(-45) == 'AORWSC'
    assert InmarsatSatellites.closest(-45, 75) == 'AMER'
    assert InmarsatSatellites.closest(0, -25) == 'EMEA'
    assert InmarsatSatellites.closest(-119) == 'AMER'
    assert InmarsatSatellites.closest(45) == 'MEAS'
    assert InmarsatSatellites.closest(45, 41) == 'EMEA'
    assert InmarsatSatellites.closest(89) == 'MEAS'
    assert InmarsatSatellites.closest(89, -4.5) == 'APAC'
