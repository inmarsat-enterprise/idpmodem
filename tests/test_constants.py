from idpmodem.constants import WakeupPeriod, PowerMode


def test_wakeup_is_valid():
    for i in range(0, 11):
        assert WakeupPeriod.is_valid(i)
    assert not WakeupPeriod.is_valid(12)
