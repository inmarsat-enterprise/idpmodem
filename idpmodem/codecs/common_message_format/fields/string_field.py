from warnings import warn

from .. import ET
from .base_field import FieldCodec
from .helpers import decode_field_length, encode_field_length


class StringField(FieldCodec):
    """A character string sent over-the-air."""
    def __init__(self,
                 name: str,
                 size: int,
                 description: str = None,
                 optional: bool = False,
                 fixed: bool = False,
                 default: str = None,
                 value: str = None) -> None:
        """Instantiates a StringField.
        
        Args:
            name: The field name must be unique within a Message.
            size: The maximum number of characters in the string.
            description: An optional description/purpose for the string.
            optional: Indicates if the string is optional in the Message.
            fixed: Indicates if the string is always fixed length `size`.
            default: A default value for the string.
            value: Optional value to set during initialization.

        """
        super().__init__(name=name,
                         data_type='string',
                         description=description,
                         optional=optional)
        self._size = size
        self._fixed = fixed
        self._default = default
        self._value = value if value is not None else self._default
    
    def _validate_string(self, s: str) -> str:
        if s is not None:
            if not isinstance(s, str):
                raise ValueError(f'Invalid string {s}')
            if len(s) > self.size:
                warn(f'Clipping string at max {self.size} characters')
                return s[:self.size]
        return s
                
    @property
    def size(self) -> int:
        """The maximum size of the string in characters."""
        return self._size
    
    @size.setter
    def size(self, value: int):
        if not isinstance(value, int) or value < 1:
            raise ValueError('Size must be integer greater than 0 characters')
        self._size = value
    
    @property
    def default(self) -> str:
        """The default value."""
        return self._default
    
    @default.setter
    def default(self, v: str):
        self._default = self._validate_string(v)

    @property
    def value(self) -> str:
        return self._value
    
    @value.setter
    def value(self, v: str):
        self._value = self._validate_string(v)

    @property
    def fixed(self) -> bool:
        """Indicates whether the string length is fixed (padded/truncated)."""
        return self._fixed
    
    @fixed.setter
    def fixed(self, value: bool):
        self._fixed = value

    @property
    def bits(self) -> int:
        """The size of the field in bits."""
        if self._value is None:
            bits = 0
        elif self.fixed:
            bits = self.size * 8
        else:
            L = 8 if len(self._value) < 127 else 16
            bits = L + len(self._value) * 8
        return bits + (1 if self.optional else 0)
    
    def encode(self) -> str:
        """Returns the binary string of the field value."""
        if self.value is None and not self.optional:
            raise ValueError(f'No value defined for StringField {self.name}')
        binstr = ''.join(format(ord(c), '08b') for c in self.value)
        if self.fixed:
            binstr += ''.join('0' for bit in range(len(binstr), self.bits))
        else:
            binstr = encode_field_length(len(self.value)) + binstr
        return binstr

    def decode(self, binary_str: str) -> int:
        """Populates the field value from binary and returns the next offset.
        
        Args:
            binary_str (str): The binary string to decode
        
        Returns:
            The bit offset after parsing
        """
        if self.fixed:
            length = self.size
            bit_index = 0
        else:
            (length, bit_index) = decode_field_length(binary_str)
        n = int(binary_str[bit_index:bit_index + length * 8], 2)
        char_bytes = n.to_bytes((n.bit_length() + 7) // 8, 'big')
        for i, byte in enumerate(char_bytes):
            if byte == 0:
                warn('Truncating after 0 byte in string')
                char_bytes = char_bytes[:i]
                break
        self.value = char_bytes.decode('utf-8', 'surrogatepass') or '\0'
        return bit_index + length * 8

    def xml(self) -> ET.Element:
        """Returns the String XML definition for a Message Definition File."""
        xmlfield = self._base_xml()
        size = ET.SubElement(xmlfield, 'Size')
        size.text = str(self.size)
        if self.fixed:
            fixed = ET.SubElement(xmlfield, 'Fixed')
            fixed.text = 'true'
        if self.default:
            default = ET.SubElement(xmlfield, 'Default')
            default.text = str(self.default)
        return xmlfield
