import os
import logging

import pytest
from idpmodem.threaded.atcommand import AtProtocol, ByteReaderThread, Serial
from idpmodem.aterror import AtTimeout, AtCrcError

SERIAL_PORT = os.getenv('SERIAL_PORT', '/dev/ttyUSB0')
logger = logging.getLogger(__name__)
logger.propagate = True


class SimpleModem:
    def __init__(self) -> None:
        self.serial_port = Serial(SERIAL_PORT)
        self.main_thread = ByteReaderThread(self.serial_port, AtProtocol)
        self.main_thread.start()
        self.transport, self.protocol = self.main_thread.connect()


@pytest.fixture
def modem():
    return SimpleModem()


def test_basic(modem):
    protocol: AtProtocol = modem.protocol
    res = protocol.command('AT')
    assert isinstance(res, list)
    assert res[0] == 'OK'


def test_timeout(modem):
    protocol: AtProtocol = modem.protocol
    with pytest.raises(AtTimeout) as err:
        res = protocol.command('AT')


def test_filter_ok(modem):
    protocol: AtProtocol = modem.protocol
    res = protocol.command('AT', filter=['OK'])
    assert len(res) == 0


def test_badcommand(modem):
    protocol: AtProtocol = modem.protocol
    res = protocol.command('ATP')
    assert res[0] == 'ERROR'


def test_unsolicited_nocallback(modem, caplog):
    protocol: AtProtocol = modem.protocol
    with caplog.at_level(logging.WARNING):
        while 'event' not in caplog.text.lower():
            pass
        assert 'event' in caplog.text


def unsolicited_callback(text: str):
    logging.info(f'Callback received event: {text}')


def test_unsolicited_callback(modem, caplog):
    protocol: AtProtocol = modem.protocol
    protocol.event_callback = unsolicited_callback
    with caplog.at_level(logging.INFO):
        while 'callback' not in caplog.text.lower():
            pass
        assert 'callback' in caplog.text.lower()


def test_gnss_immediate_timeout(modem):
    protocol: AtProtocol = modem.protocol
    res = protocol.command('AT%GPS=1,35,"RMC","GSA","GGA","GSV"')
    assert res is not None
    err_code = protocol.command('ATS80?')
    assert err_code[0] == '108'


def test_gnss_immediate_timeout_crc(modem):
    protocol: AtProtocol = modem.protocol
    crc_enabled = protocol.command('AT%CRC=1')
    res = protocol.command('AT%GPS=1,35,"RMC","GSA","GGA","GSV"')
    assert res is not None
    err_code = protocol.command('ATS80?')
    assert err_code[0] == '108'
