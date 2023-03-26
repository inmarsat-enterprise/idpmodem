import json
import logging
import os
from datetime import datetime
from time import sleep

import pytest
import pytest_mock

from idpmodem.constants import *
from idpmodem.location import Location
from idpmodem.threaded.modem import IdpModem

SERIAL_PORT = os.getenv('SERIAL_PORT', '/dev/ttyUSB0')
TEST_NMEA = [
    '$GPRMC,152332.000,A,4517.1048,N,07550.9152,W,0.03,0.00,150422,,,A,V*03',
    '$GPGGA,152332.000,4517.1048,N,07550.9152,W,1,06,2.1,125.2,M,-34.3,M,,0000*60',
    '$GPGSA,A,3,08,07,09,21,04,14,,,,,,,3.1,2.1,2.3,1*2B',
    '$GPGSV,2,1,08,01,05,166,35,04,08,189,32,07,66,295,30,08,80,107,26,0*68',
    '$GPGSV,2,2,08,09,25,218,43,14,11,271,38,21,28,141,37,27,45,053,33,0*6E',
]
TEST_LOCATION = {
    'latitude': 45.28508,
    'longitude': -75.848587,
}


_log = logging.getLogger(__name__)


@pytest.fixture
def modem_mock() -> IdpModem:
    modem = IdpModem(None)
    yield modem


@pytest.fixture
def modem_connected() -> IdpModem:
    modem = IdpModem(SERIAL_PORT)
    modem.connect()
    yield modem
    modem.disconnect()


def test_modem_init(modem_connected: IdpModem):
    assert modem_connected.connected is True
    assert modem_connected.config_init() is True


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


def test_no_connection():
    modem = IdpModem(None)
    assert modem.connected is False


def test_connection(modem_connected: IdpModem):
    assert modem_connected.connected


def test_mobile_id(modem_mock: IdpModem, mocker):
    TEST_ID = '00000000SKYEE3D'
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=[TEST_ID, 'OK'])
    assert modem_mock.mobile_id == TEST_ID


def test_versions(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['1,2,3', 'OK'])
    assert modem_mock.versions == {'firmware': '1', 'hardware': '2', 'at': '3'}


def test_manufacturer(modem_mock: IdpModem, mocker):
    TEST_MFR = 'Acme Company Ltd'
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=[TEST_MFR, 'OK'])
    assert modem_mock.manufacturer == TEST_MFR


def test_model(modem_mock: IdpModem, mocker):
    TEST_MODEL = 'IDP100'
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=[TEST_MODEL, 'OK'])
    assert modem_mock.model == TEST_MODEL


def test_power_mode(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['0', 'OK'])
    assert modem_mock.power_mode == PowerMode(0)


def test_set_power_mode(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['OK'])
    modem_mock.power_mode = PowerMode(1)
    modem_mock.atcommand.assert_called_with('ATS50=1')


def test_wakeup_period(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['0', 'OK'])
    assert modem_mock.wakeup_period == WakeupPeriod(0)


def test_set_wakeup_period(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['OK'])
    modem_mock.wakeup_period = WakeupPeriod(1)
    modem_mock.atcommand.assert_called_with('ATS51=1')


def test_temperature(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['350', 'OK'])
    assert modem_mock.temperature == 35.0


def test_gnss_refresh(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['0', 'OK'])
    assert modem_mock.gnss_refresh_interval == 0


def test_set_gnss_refresh(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['OK'])
    modem_mock.gnss_refresh_interval = 30
    modem_mock.atcommand.assert_called_with('AT%TRK=30,1')


def test_location(modem_mock: IdpModem, mocker):
    TEST_NMEA.append('OK')
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=TEST_NMEA)
    loc = modem_mock.location
    assert isinstance(loc, Location)
    assert loc.latitude == TEST_LOCATION['latitude']
    sleep(0.5)
    assert loc.longitude == TEST_LOCATION['longitude']
    modem_mock.atcommand.call_count == 1
    sleep (0.6)
    assert loc.latitude == TEST_LOCATION['latitude']
    modem_mock.atcommand.call_count == 2


def test_location_get(modem_mock: IdpModem, mocker):
    TEST_NMEA.append('OK')
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=TEST_NMEA)
    loc_prop = modem_mock.location
    loc_got = modem_mock.location_get()
    modem_mock.atcommand.call_count == 2
    assert loc_prop.latitude == TEST_LOCATION['latitude']
    assert loc_got.latitude == TEST_LOCATION['latitude']
    sleep(1.2)
    assert loc_prop.latitude == TEST_LOCATION['latitude']
    assert loc_got.latitude == TEST_LOCATION['latitude']
    modem_mock.atcommand.call_count == 3


def test_gnss_timeout(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['ERROR', 'TIMEOUT (108)'])
    assert modem_mock.location is None


def test_gnss_jamming_no(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['0000000000', 'OK'])
    assert modem_mock.gnss_jamming is False


def test_gnss_jamming_yes(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['0000000004', 'OK'])
    assert modem_mock.gnss_jamming is True


def test_gnss_mode(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['0000000000', 'OK'])
    assert modem_mock.gnss_mode == GnssMode(0)


def test_gnss_mode_set(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['OK'])
    modem_mock.gnss_mode = GnssMode(1)
    modem_mock.atcommand.assert_called_with('ATS39=1')


def test_transmitter_status(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['0000000005', 'OK'])
    assert modem_mock.transmitter_status == TransmitterStatus(5)


def test_registered(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['0000004400', '0000000010', '0000000000', 'OK'])
    assert modem_mock.registered is True


def test_control_state(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['0000004400', '0000000010', '0000000000', 'OK'])
    assert isinstance(modem_mock.control_state, int)


def test_network_status(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['0000004400', '0000000010', '0000000000', 'OK'])
    assert modem_mock.network_status == 'ACTIVE'


def test_snr(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['0000004400', '0000000010', '0000000000', 'OK'])
    assert modem_mock.snr == 44.0


def test_signal_quality(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['0000004400', '0000000010', '0000000000', 'OK'])
    assert modem_mock.signal_quality == SignalQuality.GOOD


def test_beamsearch(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['0000004400', '0000000010', '0000000000', 'OK'])
    assert modem_mock.beamsearch == 'IDLE'


def test_cached_multi_status(modem_mock: IdpModem, mocker):
    rv = ['0000004400', '0000000010', '0000000000', 'OK']
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=rv)
    assert modem_mock.control_state == SatlliteControlState.ACTIVE
    assert modem_mock.network_status == 'ACTIVE'
    assert modem_mock.registered is True
    assert modem_mock.beamsearch == 'IDLE'
    assert modem_mock.snr == 44.0
    assert modem_mock.signal_quality == SignalQuality.GOOD
    modem_mock.atcommand.assert_called_once_with('ATS90=3 S91=1 S92=1 S116? S122? S123?')


def test_satellite(modem_mock: IdpModem, mocker):
    rv = ['0000000016', '0000004529', '4294959712', '0000000820']
    rv.append('OK')
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=rv)
    assert modem_mock.satellite == 'AMER'


def test_utc_time(modem_mock: IdpModem, mocker):
    TEST_TIME = datetime.utcnow().isoformat()[:19]
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=[TEST_TIME.replace('T', ' '), 'OK'])
    assert modem_mock.utc_time == TEST_TIME + 'Z'


def test_cached_status(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['0000004400', '0000000010', '0000000000', 'OK'])
    assert modem_mock.control_state == 10
    sleep(0.5)
    assert modem_mock.snr == 44.0
    assert modem_mock.atcommand.call_count == 1


def test_cached_status_expired(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['0000004400', '0000000010', '0000000000', 'OK'])
    assert modem_mock.control_state == 10
    sleep(1.2)
    assert modem_mock.snr == 44.0
    assert modem_mock.atcommand.call_count == 2

    
def test_gnss_nmea_get(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.gnss_nmea_get',
                 return_value=TEST_NMEA)
    nmea = modem_mock.gnss_nmea_get()
    assert nmea == TEST_NMEA


def test_message_send_bytes(modem_mock: IdpModem, mocker):
    TEST_MSG = b'Hello World'
    TEST_DATA = bytearray([128, 1, len(TEST_MSG)]) + TEST_MSG
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['OK'])
    res = modem_mock.message_mo_send(TEST_DATA)
    assert isinstance(res, str)


def test_message_send_text(modem_mock: IdpModem, mocker):
    TEST_MSG = 'Hello World'
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['OK'])
    res = modem_mock.message_mo_send(TEST_MSG, sin=128, min=0)
    assert isinstance(res, str)


def test_message_send_large(modem_mock: IdpModem, mocker):
    TEST_DATA = bytes(b'A'*6400)
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['OK'])
    res = modem_mock.message_mo_send(TEST_DATA)
    assert isinstance(res, str)


def test_s_register_get(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['0000000000', 'OK'])
    assert modem_mock.s_register_get(50) == 0
    modem_mock.atcommand.assert_called_with('ATS50?')


def test_event_notification_monitor(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['01030', 'OK'])
    monitored = modem_mock.event_notification_monitor
    assert EventNotification.MESSAGE_MO_COMPLETE in monitored
    assert EventNotification.MESSAGE_MT_RECEIVED in monitored
    assert EventNotification.EVENT_TRACE_CACHED in monitored


def test_event_notification_monitor_set(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['OK'])
    to_monitor = [
        EventNotification.MESSAGE_MO_COMPLETE,
        EventNotification.MESSAGE_MT_RECEIVED,
        EventNotification.EVENT_TRACE_CACHED,
    ]
    modem_mock.event_notification_monitor = to_monitor
    modem_mock.atcommand.assert_called_with('ATS88=1030')


def test_event_notifications(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['01305', 'OK'])
    events = modem_mock.event_notifications
    assert len(events) == 5
    assert EventNotification.EVENT_TRACE_CACHED in events
    assert EventNotification.GNSS_FIX_NEW in events
    assert EventNotification.NETWORK_REGISTERED in events
    assert EventNotification.MODEM_RESET_COMPLETE in events
    assert EventNotification.UTC_TIME_SYNC in events


def test_trace_event_monitor(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['3.1*,3.2', 'OK'])
    trace_monitor = modem_mock.trace_event_monitor
    assert isinstance(trace_monitor, list) and len(trace_monitor) == 2
    assert (3, 1) in trace_monitor
    assert (3, 2) in trace_monitor


def test_trace_event_monitor_set(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['OK'])
    modem_mock.trace_event_monitor = [(3, 1), (3, 2)]
    modem_mock.atcommand.assert_called_with('AT%EVMON=3.1,3.2')


def test_trace_events_cached(modem_mock: IdpModem, mocker):
    mocker.patch('idpmodem.threaded.modem.IdpModem.atcommand',
                 return_value=['3.1*,3.2', 'OK'])
    cached = modem_mock.trace_events_cached
    assert isinstance(cached, list) and len(cached) == 1
    assert (3, 1) in cached


# ----- Below tests must be connected to live modem when rebooted -----
unsolicited_data = ''


def unsolicited_callback(data: str):
    global unsolicited_data
    unsolicited_data += data
    _log.info(f'Unsolicited data: {unsolicited_data}')


def test_unsolicited(modem_connected: IdpModem):
    global unsolicited_data
    assert modem_connected.connected
    modem_connected.register_unsolicited_callback(unsolicited_callback)
    modem_connected.atcommand('AT%EXIT=5')
    while ' AT ' not in unsolicited_data:
        if unsolicited_data == '':
            modem_connected.atcommand('\x18')
        pass
    assert isinstance(unsolicited_data, str) and len(unsolicited_data) > 0
