from struct import pack, unpack
from warnings import warn

from .. import ET
from .base_field import FieldCodec
from .helpers import decode_field_length, encode_field_length


class DataField(FieldCodec):
    """A data field of raw bytes sent over-the-air.
    
    Can also be used to hold floating point, double-precision or large integers.

    """
    SUPPORTED_DATA_TYPES = ['data', 'float', 'double']
    def __init__(self,
                 name: str,
                 size: int,
                 data_type: str = 'data',
                 precision: int = None,
                 description: str = None,
                 optional: bool = False,
                 fixed: bool = False,
                 default: bytes = None,
                 value: bytes = None) -> None:
        """Instantiates a EnumField.
        
        Args:
            name: The field name must be unique within a Message.
            size: The maximum number of bytes to send over-the-air.
            data_type: The data type represented within the bytes.
            precision: The number of decimal places for float/double.
            description: An optional description/purpose for the field.
            optional: Indicates if the field is optional in the Message.
            fixed: Indicates if the data bytes are a fixed `size`.
            default: A default value for the enum.
            value: Optional value to set during initialization.

        """
        if data_type is None or data_type not in self.SUPPORTED_DATA_TYPES:
            raise ValueError(f'Invalid data type {data_type}')
        super().__init__(name=name,
                         data_type=data_type,
                         description=description,
                         optional=optional)
        self._fixed = fixed
        self._size = None
        self._default = None
        self._precision = None
        self._value = None
        self.precision = precision
        self.size = size
        self.default = default
        self.value = value
    
    @property
    def size(self) -> int:
        """The maximum size of the field in bytes."""
        return self._size
    
    @size.setter
    def size(self, value: int):
        if not isinstance(value, int) or value < 1:
            raise ValueError('Size must be integer greater than 0 bytes')
        if self.data_type == 'float':
            if value != 4:
                warn('Adjusting float size to 4 bytes fixed')
            self._size = 4
            self._fixed = True
        elif self.data_type == 'double':
            if value != 8:
                warn('Adjusting double size to 8 bytes fixed')
            self._size = 8
            self._fixed = True
        else:
            self._size = value
    
    def _validate_data(self, v: 'bytes|float') -> bytes:
        """Ensures the data is of the target field size and encoding."""
        data_type = self.data_type
        if not ((isinstance(v, bytes) and data_type == 'data') or
                (isinstance(v, float) and data_type in ['float', 'double'])):
            raise ValueError(f'Data {type(v)} does not match {data_type}')
        if data_type in ['float', 'double']:
            _format = '!f' if data_type == 'float' else '!d'
            v = pack(_format, v)
        assert isinstance(v, bytes)
        if self.fixed:
            if len(v) > self.size:
                warn(f'Truncating data to {self.size} bytes')
                return v[0:self.size]
            elif len(v) < self.size:
                warn(f'Padding data to {self.size} bytes')
                return v.ljust(self.size, b'\0')
        return v

    def _convert_to_float(self, v: bytes) -> 'float|None':
        if self.data_type not in ('float', 'double') or v is None:
            return None
        convertor = '!f' if self.data_type == 'float' else '!d'
        converted = unpack(convertor, v)[0]
        if self.precision:
            converted = round(converted, self.precision)
        return converted

    @property
    def default(self) -> 'bytes|float':
        """The default value, converted for float or double data types."""
        if self.data_type in ['float', 'double']:
            return self._convert_to_float(self._default)
        return self._default
    
    @default.setter
    def default(self, v: 'bytes|float'):
        if v is None:
            self._default = None
        else:
            self._default = self._validate_data(v)

    @property
    def precision(self) -> 'int|None':
        """The number of decimal places for `float` or `double` data types."""
        return self._precision
    
    @precision.setter
    def precision(self, value: 'int|None'):
        if self.data_type in ['float', 'double']:
            if value is not None and not isinstance(value, int):
                raise ValueError('Precision must be int or None'
                                 ' for float/double data_type')
        elif value is not None:
            raise ValueError('Precision only valid for float/double data_type')
        self._precision = value

    @property
    def converted_value(self) -> 'float|None':
        """The converted value for `float` and `double` data types."""
        return self._convert_to_float(self._value)
    
    @property
    def value(self):
        """The raw binary value."""
        return self._value

    @value.setter
    def value(self, v: 'bytes|float'):
        if v is None:
            self._value = None
        else:
            self._value = self._validate_data(v)

    @property
    def fixed(self) -> bool:
        """Indicates if the field is fixed size (padded/truncated)."""
        return self._fixed

    @property
    def bits(self):
        """The size of the field in bits."""
        if self.fixed:
            return self.size * 8
        elif self._value is None:
            return 1 if self.optional else 0
        L = 8 if len(self._value) < 127 else 16
        return L + len(self._value) * 8 + (1 if self.optional else 0)
    
    def encode(self) -> str:
        """Returns the binary string of the field value."""
        if self.value is None and not self.optional:
            raise ValueError(f'No value defined for DataField {self.name}')
        binstr = ''
        binstr = ''.join(format(b, '08b') for b in self._value)
        if self.fixed:   #:pad to fixed length
            binstr += ''.join('0' for bit in range(len(binstr), self.bits))
        else:
            binstr = encode_field_length(len(self._value)) + binstr
        return binstr

    def decode(self, binary_str: str) -> int:
        """Populates the field value from binary and returns the next offset.
        
        Args:
            binary_str (str): The binary string to decode
        
        Returns:
            The bit offset after parsing
        """
        if self.fixed:
            binary = binary_str[:self.bits]
            bits = self.bits
        else:
            (length, bit_index) = decode_field_length(binary_str)
            binary = binary_str[bit_index:length * 8 + bit_index]
            bits = len(binary)
        self._value = int(binary, 2).to_bytes(int(bits / 8), 'big')
        return self.bits

    def xml(self) -> ET.Element:
        """Returns the Data XML definition for a Message Definition File."""
        xmlfield = self._base_xml()
        size = ET.SubElement(xmlfield, 'Size')
        size.text = str(self.size)
        if self.default:
            default = ET.SubElement(xmlfield, 'Default')
            default.text = str(self.default)
        return xmlfield
