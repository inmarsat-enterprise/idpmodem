# -*- coding: utf-8 -*-
"""IsatData Pro modem constants.

This module provides mapping of constants used within an IDP modem.

"""

from enum import Enum, IntEnum, IntFlag


class MessagePriority(IntEnum):
    NONE = 0
    HIGH = 1
    MEDH = 2
    MEDL = 3
    LOW = 4


class DataFormat(IntEnum):
    TEXT = 1
    HEX = 2
    BASE64 = 3


CONTROL_STATES = {
    0: 'Stopped',
    1: 'Waiting for GNSS fix',
    2: 'Starting search',
    3: 'Beam search',
    4: 'Beam found',
    5: 'Beam acquired',
    6: 'Beam switch in progress',
    7: 'Registration in progress',
    8: 'Receive only',
    9: 'Downloading Bulletin Board',
    10: 'Active',
    11: 'Blocked',
    12: 'Confirm previously registered beam',
    13: 'Confirm requested beam',
    14: 'Connect to confirmed beam'
}


class SatlliteControlState(IntEnum):
    STOPPED = 0
    GNSS_WAIT = 1
    SEARCH_START = 2
    BEAM_SEARCH = 3
    BEAM_FOUND = 4
    BEAM_ACQUIRED = 5
    BEAM_SWITCH = 6
    REGISTERING = 7
    RECEIVE_ONLY = 8
    BB_DOWNLOAD = 9
    ACTIVE = 10
    BLOCKED = 11
    CONFIRM_PREVIOUS_BEAM = 12
    CONFIRM_REQUESTED_BEAM = 13
    CONNECT_CONFIRMED_BEAM = 14


class BeamSearchState(IntEnum):
    IDLE = 0
    SEARCH_ANY_TRAFFIC = 1
    SEARCH_LAST_TRAFFIC = 2
    RESERVED = 3
    SEARCH_NEW_TRAFFIC = 4
    SEARCH_BULLETIN_BOARD = 5
    DELAY_TRAFFIC_SEARCH = 6


class MessageState(IntEnum):
    UNAVAILABLE = 0
    RX_PENDING = 1
    RX_COMPLETE = 2
    RX_RETRIEVED = 3
    TX_READY = 4
    TX_SENDING = 5
    TX_COMPLETE = 6
    TX_FAILED = 7
    TX_CANCELLED = 8


AT_ERROR_CODES = {
    0: 'OK',
    4: 'ERROR',
    100: 'ERR_INVALID_CRC_SEQUENCE',
    101: 'ERR_UNKNOWN_COMMAND',
    102: 'ERR_INVALID_COMMAND_PARAMETERS',
    103: 'ERR_MESSAGE_LENGTH_EXCEEDS_FORMAT_SIZE',
    104: 'ERR_RESERVED_104',
    105: 'ERR_SYSTEM_ERROR',
    106: 'ERR_QUEUE_INSUFFICIENT_RESOURCES',
    107: 'ERR_MESSAGE_NAME_ALREADY_IN_USE',
    108: 'ERR_TIMEOUT_OCCURRED',
    109: 'ERR_UNAVAILABLE',
    110: 'ERR_RESERVED_110',
    111: 'ERR_RESERVED_111',
    112: 'ERR_ATTEMPT_TO_WRITE_READ_ONLY_PARAMETER'
}


WAKEUP_PERIODS = {
    0: 'SECONDS_5',
    1: 'SECONDS_30',
    2: 'MINUTES_1',
    3: 'MINUTES_3',
    4: 'MINUTES_10',
    5: 'MINUTES_30',
    6: 'MINUTES_60',
    7: 'MINUTES_2',
    8: 'MINUTES_5',
    9: 'MINUTES_15',
    10: 'MINUTES_20'
}

POWER_MODES = {
    0: 'MOBILE_POWERED',
    1: 'FIXED_POWERED',
    2: 'MOBILE_BATTERY',
    3: 'FIXED_BATTERY',
    4: 'MOBILE_MINIMAL',
    5: 'MOBILE_PARKED'
}


class IdpEnum(IntEnum):
    @classmethod
    def is_valid(cls, value: int) -> bool:
        """True if the value exists in the enumeration."""
        return value in [v.value for v in cls.__members__.values()]


class AtErrorCode(IdpEnum):
    OK = 0
    ERROR = 4
    INVALID_CRC = 100
    UNKNOWN_COMMAND = 101
    INVALID_COMMAND_PARAMETERS = 102
    MESSAGE_LENGTH_EXCEEDS_FORMAT_SIZE = 103
    RESERVED_104 = 104
    SYSTEM_ERROR = 105
    QUEUE_INSUFFICIENT_RESOURCES = 106
    DUPLICATE_MESSAGE_NAME = 107
    GNSS_TIMEOUT = 108
    MESSAGE_UNAVAILABLE = 109
    RESERVED_110 = 110
    RESERVED_111 = 111
    READ_ONLY_PARAMETER = 112


class PowerMode(IdpEnum):
    MOBILE_POWERED = 0
    FIXED_POWERED = 1
    MOBILE_BATTERY = 2
    FIXED_BATTERY = 3
    MOBILE_MINIMAL = 4
    MOBILE_PARKED = 5

    def gnss_refresh_hours(self):
        """The minimum GNSS refresh interval [hours]."""
        if self.value == 0:
            return 3
        if self.value == 1:
            return 24
        if self.value == 2:
            return 6
        if self.value == 3:
            return 14 * 24
        if self.value == 4:
            return 12
        if self.value == 5:
            return 24
    
    def transmit_lifetime_seconds(self):
        """The maximum duration of a message in the transmit queue [seconds]."""
        if self.value in [0, 1]:
            return 3 * 3600
        return  3 * 60
    
    def beam_search_interval_seconds(self):
        """The minimum time between background beam searches [seconds]."""
        if self.value in [0, 2, 4]:
            return 20 * 60
        return 60 * 60

    def short_term_blockage_seconds(self):
        """The time in blockage before initiating a beam search [seconds]."""
        if self.value in [0, 1]:
            return 5 * 60
        if self.value in [2, 3, 4]:
            return 20 * 60
        return 15 * 60
    
    def beam_search_maximum_seconds(self):
        """The maximum backoff interval between searches when blocked [seconds].
        """
        if self.value in [0, 1]:
            return 0
        return 1600 * 60


class WakeupPeriod(IdpEnum):
    SECONDS_5 = 0
    SECONDS_30 = 1
    MINUTES_1 = 2
    MINUTES_3 = 3
    MINUTES_10 = 4
    MINUTES_30 = 5
    MINUTES_60 = 6
    MINUTES_2 = 7
    MINUTES_5 = 8
    MINUTES_15 = 9
    MINUTES_20 = 10

    def seconds(self):
        value = int(self.name.split('_'))[1]
        if self.name.startswith('MINUTES'):
            return value * 60
        return value


class GnssMode(IdpEnum):
    GPS = 0
    GLONASS = 1
    BEIDOU = 2
    GALILEO = 3
    GPS_GLONASS = 10
    GPS_BEIDOU = 11
    GLONASS_BEIDOU = 12
    GPS_GALILEO = 13
    GLONASS_GALILEO = 14
    BEIDOU_GALILEO = 15


# Dynamic Platform Model - use with caution
GNSS_DPM_MODES = {
    0: 'PORTABLE',
    2: 'STATIONARY',
    3: 'PEDESTRIAN',
    4: 'AUTOMOTIVE',
    5: 'SEA',
    6: 'AIR_1G',
    7: 'AIR_2G',
    8: 'AIR_4G'
}


class SignalLevelRegional(Enum):
    """Qualitative descriptors for SNR/CN0 values for a IDP Regional Beam.
    
    BARS_n: *n* is a scale from 0..5 to be used as greaterThan threshold
    NONE, MARGINAL, GOOD: a scale to be used as greaterOrEqual threshold

    """
    BARS_0 = 0
    BARS_1 = 37.0
    BARS_2 = 39.0
    BARS_3 = 41.0
    BARS_4 = 43.0
    BARS_5 = 45.5
    INVALID = 55.0


class SignalQuality(IntEnum):
    NONE = 0
    WEAK = 1
    LOW = 2
    MID = 3
    GOOD = 4
    STRONG = 5
    WARNING = 6


class EventNotification(IntFlag):
    GNSS_FIX_NEW = 0b000000000001
    MESSAGE_MT_RECEIVED = 0b000000000010
    MESSAGE_MO_COMPLETE = 0b000000000100
    NETWORK_REGISTERED = 0b000000001000
    MODEM_RESET_COMPLETE = 0b000000010000
    JAMMING_ANTENNA_CHANGE = 0b000000100000
    MODEM_RESET_PENDING = 0b000001000000
    WAKEUP_PERIOD_CHANGE = 0b000010000000
    UTC_TIME_SYNC = 0b000100000000
    GNSS_FIX_TIMEOUT = 0b001000000000
    EVENT_TRACE_CACHED = 0b010000000000
    NETWORK_PING_ACKNOWLEDGED = 0b100000000000


class TransmitterStatus(IdpEnum):
    RX_ONLY_NOT_REGISTERED = 4
    OK = 5
    SUSPENDED = 6
    MUTED = 7
    BLOCKED = 8


class EventTraceClass(IdpEnum):
    HARDWARE_FAULT = 1
    SYSTEM = 2
    SATELLITE = 3
    GNSS = 4
    MESSAGE = 5


class EventTraceSubclass(IdpEnum):
    """Base class for trace subclasses"""


class EventTraceSystem(EventTraceSubclass):
    RESET = 1
    LOW_POWER = 2
    SYSTEM_STATS = 3
    SATCOM_STATS = 4


class EventTraceSatellite(EventTraceSubclass):
    RX_STATUS = 1
    TX_STATUS = 2
    BEAM_CONNECT = 3
    BEAM_SEARCH_RESULT = 4
    GEO_ADJUST = 5
    EVENT_LOG = 6
    RX_METRICS_SUBFRAME = 16
    RX_METRICS_MINUTE = 17
    RX_METRICS_HOUR = 18
    RX_METRICS_DAY = 19
    TX_METRICS_SUBFRAME = 20
    TX_METRICS_MINUTE = 21
    TX_METRICS_HOUR = 22
    TX_METRICS_DAY = 23


class EventTraceGnss(EventTraceSubclass):
    FIX_STATS = 1
    DOPPLER = 4


class EventTraceMessage(EventTraceSubclass):
    RECEIVE_STATS = 1
    TRANSMIT_STATS = 2
    TRANSMIT_UTILITY = 3


class EventTrace:
    def __init__(self,
                 trace_class: EventTraceClass,
                 trace_subclass: EventTraceSubclass,
                 data: 'tuple[str, str|dict|IntEnum]') -> None:
        """Defines an event trace.
        
        Args:
            trace_class: The enumerated class
            trace_subclass: The enumerated subclass dependent on the class
            data: The set of (name, meta) where meta defines either a
                data type (e.g. `uint`) or a mapping (`dict` or `IntEnum`)
        """
        self.trace_class: EventTraceClass = trace_class
        self.trace_subclass: EventTraceSubclass = trace_subclass
        self.data: 'tuple[str, str|dict|IntEnum]' = data


EVENT_TRACE_SATELLITE_GENERAL = EventTrace(
    trace_class=EventTraceClass.SATELLITE,
    trace_subclass=EventTraceSatellite.RX_STATUS,
    data=(
        ('subframe_number', 'uint'),
        ('traffic_vcid', 'uint'),
        ('configuration_id', 'uint'),
        ('beam_number', 'uint'),
        ('reserved04', 'uint'),
        ('tx_access_sip', 'uint'),
        ('tx_access_operator', 'uint'),
        ('tx_access_user', 'uint'),
        ('tx_suspend_flags', {
            0x1: 'BEAM_REGISTRATION',
            0x2: 'BEAM_SWITCH',
            0x4: 'RESERVED',
            0x8: 'BLOCKED',
        }),
        ('tx_messages_active', 'uint'),
        ('tx_messages_total', 'uint'),
        ('tx_packets_active', 'uint'),
        ('tx_state', {
            0: 'ACTIVE',
            1: 'SUSPENDING',
            2: 'SUSPENDED_PENDING_GNSS'}),
        ('active_rx_messages', 'uint'),
        ('beamswitch_averaging_window', 'uint'),
        ('beamswitch_averaging_count', 'uint'),
        ('c_n_x100', 'uint'),
        ('beamsample_threshold', 'uint'),
        ('beamsample_timer', 'uint'),
        ('flags', {
            0x1: 'REGISTERED',
            0x2: 'SENDING_BEAM_REGISTRATION',
            0x10: 'BEAM_SEARCH',
            0x20: 'BEAM_SAMPLE_REQUIRED',
            0x40: 'BEAM_SWITCH_PENDING',
            0x100: 'GNSS_VALID',
            0x200: 'GNSS_REQUIRED',
            0x400: 'GNSS_PENDING',
        }),
        ('gnss_state_timer', 'uint'),
        ('reserved21', 'uint'),
        ('satellite_control_state', SatlliteControlState),
        ('beam_search_state', BeamSearchState),
    )
)


EVENT_TRACES = (
    EVENT_TRACE_SATELLITE_GENERAL,
)


GEOBEAMS = {
    1: 'AMER RB1',
    2: 'AMER RB2',
    3: 'AMER RB3',
    4: 'AMER RB4',
    5: 'AMER RB5',
    6: 'AMER RB6',
    7: 'AMER RB7',
    8: 'AMER RB8',
    9: 'AMER RB9',
    10: 'AMER RB10',
    11: 'AMER RB11',
    12: 'AMER RB12',
    13: 'AMER RB13',
    14: 'AMER RB14',
    15: 'AMER RB15',
    16: 'AMER RB16',
    17: 'AMER RB17',
    18: 'AMER RB18',
    19: 'AMER RB19',
    61: 'AORW SC',
    21: 'EMEA RB1',
    22: 'EMEA RB2',
    23: 'EMEA RB3',
    24: 'EMEA RB4',
    25: 'EMEA RB5',
    26: 'EMEA RB6',
    27: 'EMEA RB7',
    28: 'EMEA RB8',
    29: 'EMEA RB9',
    30: 'EMEA RB10',
    31: 'EMEA RB11',
    32: 'EMEA RB12',
    33: 'EMEA RB13',
    34: 'EMEA RB14',
    35: 'EMEA RB15',
    36: 'EMEA RB16',
    37: 'EMEA RB17',
    38: 'EMEA RB18',
    39: 'EMEA RB19',
    41: 'APAC RB1',
    42: 'APAC RB2',
    43: 'APAC RB3',
    44: 'APAC RB4',
    45: 'APAC RB5',
    46: 'APAC RB6',
    47: 'APAC RB7',
    48: 'APAC RB8',
    49: 'APAC RB9',
    50: 'APAC RB10',
    51: 'APAC RB11',
    52: 'APAC RB12',
    53: 'APAC RB13',
    54: 'APAC RB14',
    55: 'APAC RB15',
    56: 'APAC RB16',
    57: 'APAC RB17',
    58: 'APAC RB18',
    59: 'APAC RB19',
    90: 'MEAS RB10',
    91: 'MEAS RB11',
    92: 'MEAS RB12',
    93: 'MEAS RB15',
}


class GeoBeam(IdpEnum):
    GLOBAL_BB = 0
    AMER_RB1 = 1
    AMER_RB2 = 2
    AMER_RB3 = 3
    AMER_RB4 = 4
    AMER_RB5 = 5
    AMER_RB6 = 6
    AMER_RB7 = 7
    AMER_RB8 = 8
    AMER_RB9 = 9
    AMER_RB10 = 10
    AMER_RB11 = 11
    AMER_RB12 = 12
    AMER_RB13 = 13
    AMER_RB14 = 14
    AMER_RB15 = 15
    AMER_RB16 = 16
    AMER_RB17 = 17
    AMER_RB18 = 18
    AMER_RB19 = 19
    AORW_SC = 61
    EMEA_RB1 = 21
    EMEA_RB2 = 22
    EMEA_RB3 = 23
    EMEA_RB4 = 24
    EMEA_RB5 = 25
    EMEA_RB6 = 26
    EMEA_RB7 = 27
    EMEA_RB8 = 28
    EMEA_RB9 = 29
    EMEA_RB10 = 30
    EMEA_RB11 = 31
    EMEA_RB12 = 32
    EMEA_RB13 = 33
    EMEA_RB14 = 34
    EMEA_RB15 = 35
    EMEA_RB16 = 36
    EMEA_RB17 = 37
    EMEA_RB18 = 38
    EMEA_RB19 = 39
    APAC_RB1 = 41
    APAC_RB2 = 42
    APAC_RB3 = 43
    APAC_RB4 = 44
    APAC_RB5 = 45
    APAC_RB6 = 46
    APAC_RB7 = 47
    APAC_RB8 = 48
    APAC_RB9 = 49
    APAC_RB10 = 50
    APAC_RB11 = 51
    APAC_RB12 = 52
    APAC_RB13 = 53
    APAC_RB14 = 54
    APAC_RB15 = 55
    APAC_RB16 = 56
    APAC_RB17 = 57
    APAC_RB18 = 58
    APAC_RB19 = 59
    MEAS_RB10 = 90
    MEAS_RB11 = 91
    MEAS_RB12 = 92
    MEAS_RB15 = 93

    def satellite(self):
        return self.name.split('_')[0]

    def beam(self):
        return self.name.split('_')[1]
    
    def id(self):
        return self.value
