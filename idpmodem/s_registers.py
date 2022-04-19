"""IDP modem S-register definitions

IDP modem S-register definitions useful for creating a digital twin of the modem
Updated register map of default and configured values can be read from the modem
using AT%SREG which returns a human-readable table
"""


# Tuples: (name[0], default[1], read-only[2], range[3], description[4], note[5])
REGISTER_DEFINITIONS = [
    ('S0', 0, True, [0, 255], 'auto answer', 'unused'),
    ('S3', 13, False, [1, 127], 'command termination character', None),
    ('S4', 10, False, [0, 127], 'response formatting character', None),
    ('S5', 8, False, [0, 127], 'command line editing character', None),
    ('S6', 0, True, [0, 255], 'pause before dial', 'unused'),
    ('S7', 0, True, [0, 255], 'connection completion timeout', 'unused'),
    ('S8', 0, True, [0, 255], 'commia dial modifier time', 'unused'),
    ('S10', 0, True, [0, 255], 'automatic discovery delay', 'unused'),
    ('S31', 80, False, [10, 250], 'DOP threshold (x10)', None),
    ('S32', 25, False, [1, 1000], 'position accuracy threshold [m]', None),
    ('S33', 0, False, [0, 8], 'default dynamic platform model', None),
    ('S34', 7, True, [0, 255], 'Doppler dynamic platform model', 'Reserved'),
    ('S35', 0, False, [0, 255], 'static hold threshold [cm/s]', None),
    ('S36', 0, False, [-1, 480], 'standby timeout [min]', None),
    ('S37', 200, False, [1, 1000], 'speed accuracy threshold', None),
    ('S38', 1, True, [0, 0], 'reserved', None),
    ('S39', 0, False, [0, 2], 'GNSS mode', None),
    ('S40', 0, False, [0, 60], 'GNSS signal satellite detection timeout', None),
    ('S41', 180, False, [60, 1200], 'GNSS fix timeout', None),
    ('S42', 65535, False, [0, 65535], 'GNSS augmentation systems', 'Query fails'),
    ('S50', 0, False, [0, 9], 'power mode', None),
    ('S51', 0, False, [0, 6], 'wakeup interval', None),
    ('S52', 2500, True, [0, 2500], 'reserved', 'undocumented'),
    ('S53', 0, True, [0, 255], 'satcom control', None),
    ('S54', 0, True, [0, 0], 'satcom status', None),
    ('S55', 0, False, [0, 30], 'GNSS continuous mode', None),
    ('S56', 0, True, [0, 255], 'GNSS jamming status', None),
    ('S57', 0, True, [0, 255], 'GNSS jamming indicator', None),
    ('S60', 1, False, [0, 1], 'Echo', None),
    ('S61', 0, False, [0, 1], 'Quiet', None),
    ('S62', 1, False, [0, 1], 'Verbose', None),
    ('S63', 0, False, [0, 1], 'CRC', None),
    ('S64', 42, False, [0, 255], 'prefix character of CRC sequence', None),
    ('S70', 0, True, [0, 0], 'reserved', 'undocumented'),
    ('S71', 0, True, [0, 0], 'reserved', 'undocumented'),
    ('S80', 0, True, [0, 255], 'last error code', None),
    ('S81', 0, True, [0, 255], 'most recent result code', None),
    ('S85', 22, True, [0, 0], 'temperature', None),
    ('S88', 0, False, [0, 65535], 'event notification control', None),
    # ('S89', 0, False, [0, 65535], 'event notification status', None),
    ('S90', 0, False, [0, 7], 'capture trace define - class', None),
    ('S91', 0, False, [0, 31], 'capture trace define - subclass', None),
    ('S92', 0, False, [0, 255], 'capture trace define - initiate', None),
    ('S93', 0, True, [0, 255], 'captured trace property - data size', None),
    ('S94', 0, True, [0, 255], 'captured trace property - signed indicator', None),
    ('S95', 0, True, [0, 255], 'captured trace property - mobile ID', None),
    ('S96', 0, True, [0, 255], 'captured trace property - timestamp', None),
    ('S97', 0, True, [0, 255], 'captured trace property - class', None),
    ('S98', 0, True, [0, 255], 'captured trace property - subclass', None),
    ('S99', 0, True, [0, 255], 'captured trace property - severity', None),
    ('S100', 0, True, [0, 255], 'captured trace data 0', None),
    ('S101', 0, True, [0, 255], 'captured trace data 1', None),
    ('S102', 0, True, [0, 255], 'captured trace data 2', None),
    ('S103', 0, True, [0, 255], 'captured trace data 3', None),
    ('S104', 0, True, [0, 255], 'captured trace data 4', None),
    ('S105', 0, True, [0, 255], 'captured trace data 5', None),
    ('S106', 0, True, [0, 255], 'captured trace data 6', None),
    ('S107', 0, True, [0, 255], 'captured trace data 7', None),
    ('S108', 0, True, [0, 255], 'captured trace data 8', None),
    ('S109', 0, True, [0, 255], 'captured trace data 9', None),
    ('S110', 0, True, [0, 255], 'captured trace data 10', None),
    ('S111', 0, True, [0, 255], 'captured trace data 11', None),
    ('S112', 0, True, [0, 255], 'captured trace data 12', None),
    ('S113', 0, True, [0, 255], 'captured trace data 13', None),
    ('S114', 0, True, [0, 255], 'captured trace data 14', None),
    ('S115', 0, True, [0, 255], 'captured trace data 15', None),
    ('S116', 0, True, [0, 255], 'captured trace data 16', None),
    ('S117', 0, True, [0, 255], 'captured trace data 17', None),
    ('S118', 0, True, [0, 255], 'captured trace data 18', None),
    ('S119', 0, True, [0, 255], 'captured trace data 19', None),
    ('S120', 0, True, [0, 255], 'captured trace data 20', None),
    ('S121', 0, True, [0, 255], 'captured trace data 21', None),
    ('S122', 0, True, [0, 255], 'captured trace data 22', None),
    ('S123', 0, True, [0, 255], 'captured trace data 23', None),
]


class SRegister(object):
    """
    Twin of a modem S register
    """

    def __init__(self,
                 name: str,
                 default: int,
                 read_only: bool,
                 min: int,
                 max: int,
                 description: str,
                 note: str = None):
        """
        Initializes an S register twin

        :param name: (string) name of the S register e.g. 'S50'
        :param default: (int) default value of the register
        :param read_only: (Boolean)
        :param low: (int) lowest value allowed
        :param high: (int) highest value allowed
        :param description: (string)
        :param note: (string), defaults to None
        """
        self._name = name
        self._default = default
        self._value = default
        self._read_only = read_only
        self._min = min
        self._max = max
        self._description = description
        self._note = note

    @property
    def name(self) -> str:
        return self._name

    @property
    def default(self) -> int:
        return self._default

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, value: int):
        if self.read_only:
            raise ValueError(f'{self.name} is read-only')
        if not isinstance(value, int) or value not in self.min_max:
            raise ValueError(f'{self.name} must be {self.min}..{self.max}')
        self._value = value

    @property
    def read_only(self) -> bool:
        return self._read_only

    @property
    def min_max(self) -> range:
        return range(self._min, self._max +1)

    @property
    def min(self) -> int:
        return self._min
    
    @property
    def max(self) -> int:
        return self._max

    @property
    def description(self) -> str:
        return self._description

    @property
    def note(self) -> str:
        return self._note


class SRegisters(dict):
    """A dictionary twin of the modem's S registers."""
    def __init__(self):
        for tup in REGISTER_DEFINITIONS:
            name, dflt, ro, lo_hi, desc, note = tup
            self[name] = SRegister(name,
                                   dflt,
                                   ro,
                                   lo_hi[0],
                                   lo_hi[1],
                                   desc,
                                   note)
