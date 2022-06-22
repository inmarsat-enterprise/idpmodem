import json
import os
import pytest
import pytest_mock

from idpmodem.threaded.modem import IdpModem
from idpmodem.aterror import AtTimeout
from idpmodem.constants import *

SERIAL_PORT = os.getenv('SERIAL_PORT', '/dev/ttyUSB0')
TEST_NMEA = [
    '$GPRMC,152332.000,A,4517.1048,N,07550.9152,W,0.03,0.00,150422,,,A,V*03',
    '$GPGGA,152332.000,4517.1048,N,07550.9152,W,1,06,2.1,125.2,M,-34.3,M,,0000*60',
    '$GPGSA,A,3,08,07,09,21,04,14,,,,,,,3.1,2.1,2.3,1*2B',
    '$GPGSV,2,1,08,01,05,166,35,04,08,189,32,07,66,295,30,08,80,107,26,0*68',
    '$GPGSV,2,2,08,09,25,218,43,14,11,271,38,21,28,141,37,27,45,053,33,0*6E',
]


@pytest.fixture
def modem_connected() -> IdpModem:
    modem = IdpModem(SERIAL_PORT)
    modem.connect()
    yield modem
    modem.disconnect()


@pytest.fixture
def modem_configured(modem_connected) -> IdpModem:
    modem: IdpModem = modem_connected
    modem.config_init()
    return modem


def test_timeout(modem_connected):
    modem: IdpModem = modem_connected
    with pytest.raises(AtTimeout):
        modem.config_init()
    assert not modem.commands.full()


def test_no_connection(modem_connected):
    modem: IdpModem = modem_connected
    assert not modem.connected
    assert not modem.commands.full()


def test_connection(modem_connected):
    modem: IdpModem = modem_connected
    assert modem.connected


def test_gnss_fail(modem_configured):
    modem: IdpModem = modem_configured
    location = modem.location
    assert location is None


def test_control_state(modem_configured):
    modem: IdpModem = modem_configured
    cs = modem.control_state
    assert isinstance(cs.value, int)


def test_properties(modem_connected, mocker):
    modem: IdpModem = modem_connected
    modem.config_init(crc=False)
    mocker.patch('idpmodem.threaded.modem.IdpModem.gnss_nmea_get',
                 return_value=TEST_NMEA)
    properties = []
    for k, v in IdpModem.__dict__.items():
        if isinstance(v, property):
            properties.append(k)
    properties_to_test = {
        'connected': modem.connected,
        'baudrate': modem.baudrate,
        'crc': modem.crc,
        'mobile_id': modem.mobile_id,
        'versions': modem.versions,
        'power_mode': modem.power_mode,
        'wakeup_period': modem.wakeup_period,
        'gnss_refresh_interval': modem.gnss_refresh_interval,
        'location': modem.location,
        'control_state': modem.control_state,
        'network_status': modem.network_status,
        'registered': modem.registered,
        'beamsearch_state': modem.beamsearch_state,
        'beamsearch': modem.beamsearch,
        'snr': modem.snr,
        'signal_quality': modem.signal_quality,
        'satellite': modem.satellite,
        'beam_id': modem.beam_id,
        'temperature': modem.temperature,
        'gnss_jamming': modem.gnss_jamming,
        'gnss_mode': modem.gnss_mode,
        'transmitter_status': modem.transmitter_status,
        'trace_event_monitor': modem.trace_event_monitor,
        'trace_events_cached': modem.trace_events_cached,
        'event_notification_monitor': modem.event_notification_monitor,
        'event_notifications': modem.event_notifications,
        'manufacturer': modem.manufacturer,
        'model': modem.model,
    }
    properties_missed = [x for x in properties if x not in properties_to_test]
    assert len(properties_missed) == 0
    assert isinstance(modem.mobile_id, str)
    assert isinstance(modem.versions, dict)


def test_gnss_nmea_get(modem_configured, mocker):
    modem: IdpModem = modem_configured
    mocker.patch('idpmodem.threaded.modem.IdpModem.gnss_nmea_get',
                 return_value=TEST_NMEA)
    nmea = modem.gnss_nmea_get()
    assert nmea == TEST_NMEA


def test_baudrate():
    modem = IdpModem(SERIAL_PORT)
    with pytest.raises(ConnectionError):
        modem.baudrate = 4800
    modem.connect()
    modem.config_init()
    modem.baudrate = 4800
    assert modem.baudrate == 4800
    with pytest.raises(ValueError):
        modem.baudrate = 100
    modem.baudrate = 9600
    assert modem.baudrate == 9600
    modem.disconnect()


def test_message_send_bytes(modem_configured, mocker):
    modem: IdpModem = modem_configured
    TEST_MSG = b'Hello World'
    TEST_DATA = bytearray([128, 1, len(TEST_MSG)]) + TEST_MSG
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['OK'])
    res = modem.message_mo_send(TEST_DATA)
    assert isinstance(res, str)


def test_message_send_text(modem_configured, mocker):
    modem: IdpModem = modem_configured
    TEST_MSG = 'Hello World'
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['OK'])
    res = modem.message_mo_send(TEST_MSG, sin=128, min=0)
    assert isinstance(res, str)


def test_s_registers(modem_configured):
    modem: IdpModem = modem_configured
    modem._s_registers_read()
    for name, reg in modem.s_registers.items():
        assert isinstance(reg.value, int)


def test_event_notification_monitor(modem_configured):
    modem: IdpModem = modem_configured
    monitored = modem.event_notification_monitor
    for event in monitored:
        assert isinstance(event, EventNotification)


def test_event_notification_monitor_set(modem_configured):
    modem: IdpModem = modem_configured
    to_monitor = [
        # EventNotification.GNSS_FIX_NEW,
    ]
    modem.event_notification_monitor = to_monitor
    monitored = modem.event_notification_monitor
    assert monitored == to_monitor


def test_event_notifications(modem_configured):
    modem: IdpModem = modem_configured
    events = modem.event_notifications
    for event in events:
        assert isinstance(event, EventNotification)


def test_trace_event_monitor(modem_configured):
    modem: IdpModem = modem_configured
    trace_monitor = modem.trace_event_monitor
    for mon in trace_monitor:
        assert isinstance(mon, tuple)    


def test_trace_events_cached(modem_configured):
    modem: IdpModem = modem_configured
    cached = modem.trace_events_cached
    for trace in cached:
        assert isinstance(trace, tuple)
        detail = modem.trace_event_get(trace, meta=True)
        assert isinstance(detail, dict)


def test_transmitter_status(modem_configured):
    modem: IdpModem = modem_configured
    tstatus = modem.transmitter_status
    assert isinstance(tstatus, TransmitterStatus)


def test_location(modem_configured):
    modem: IdpModem = modem_configured
    loc = modem.location
    try:
        j = json.dumps(loc.serialize(), skipkeys=True)
    except:
        j = 'UNKNOWN'
    assert isinstance(j, str)


def test_initialization():
    modem = IdpModem(SERIAL_PORT)
    modem.connect()
    initialized = modem.config_init(crc=True)
    assert initialized
    modem.disconnect()
    modem.connect()
    reinit = modem.config_init(crc=False)
    assert reinit
    modem.protocol.crc = True
    rereinit = modem.config_init(crc=True)
    assert rereinit


unsolicited_data = None

def unsolicited_callback(data: str):
    global unsolicited_data
    unsolicited_data += data


def test_unsolicited():
    global unsolicited_data
    modem = IdpModem(SERIAL_PORT)
    modem.connect()
    modem.protocol.event_callback = unsolicited_callback
    while unsolicited_data is None:
        pass
    assert isinstance(unsolicited_data, str)
