from warnings import warn

from .. import ET
from .base_field import FieldCodec


class UnsignedIntField(FieldCodec):
    """An unsigned integer value using a defined number of bits over-the-air."""
    def __init__(self,
                 name: str,
                 size: int,
                 data_type: str = 'uint_16',
                 description: str = None,
                 optional: bool = False,
                 default: int = None,
                 value: int = None) -> None:
        """Instantiates a UnsignedIntField.
        
        Args:
            name: The field name must be unique within a Message.
            size: The number of *bits* used to encode the integer over-the-air
                (maximum 32).
            data_type: The integer type represented (for decoding).
            description: An optional description/purpose for the string.
            optional: Indicates if the string is optional in the Message.
            default: A default value for the string.
            value: Optional value to set during initialization.

        """
        if data_type not in ['uint_8', 'uint_16', 'uint_32']:
            raise ValueError(f'Invalid unsignedint type {data_type}')
        if not isinstance(size, int) or size < 1:
            raise ValueError('Size must be int greater than zero')
        super().__init__(name=name,
                         data_type=data_type,
                         description=description,
                         optional=optional)
        self._size = size
        self._default = default
        self._value = value if value is not None else self._default
    
    @property
    def size(self):
        """The size of the field in bits."""
        return self._size

    @size.setter
    def size(self, value: int):
        if not isinstance(value, int) or value < 1:
            raise ValueError('Size must be integer greater than 0 bits')
        data_type_size = int(self.data_type.split('_')[1])
        if value > data_type_size:
            warn(f'Size {value} larger than required by {self.data_type}')
        self._size = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v: int):
        clip = False
        if v is not None:
            if not isinstance(v, int) or v < 0:
                raise ValueError('Unsignedint must be non-negative integer')
            if v > 2**self.size - 1:
                self._value = 2**self.size - 1
                warn(f'Clipping unsignedint at max value {self._value}')
                clip = True
        if not clip:
            self._value = v
    
    @property
    def default(self):
        """The default value."""
        return self._default
    
    @default.setter
    def default(self, v: int):
        if v is not None:
            if v > 2**self.size - 1 or v < 0:
                raise ValueError(F'Invalid unsignedint default {v}')
        self._default = v
    
    @property
    def bits(self):
        """The size of the field in bits."""
        bits = self.size if self._value is not None else 0
        return bits + (1 if self.optional else 0)
    
    def encode(self) -> str:
        """Returns the binary string of the field value."""
        if self.value is None:
            raise ValueError(f'No value defined in UnsignedIntField {self.name}')
        _format = f'0{self.size}b'
        return format(self.value, _format)

    def decode(self, binary_str: str) -> int:
        """Populates the field value from binary and returns the next offset.
        
        Args:
            binary_str (str): The binary string to decode
        
        Returns:
            The bit offset after parsing
        """
        self.value = int(binary_str[:self.size], 2)
        return self.size

    def xml(self) -> ET.Element:
        """Returns the UnsignedInt XML definition for a Message Definition File.
        """
        xmlfield = self._base_xml()
        size = ET.SubElement(xmlfield, 'Size')
        size.text = str(self.size)
        if self.default:
            default = ET.SubElement(xmlfield, 'Default')
            default.text = str(self.default)
        return xmlfield


class SignedIntField(FieldCodec):
    """A signed integer value using a defined number of bits over-the-air."""
    def __init__(self,
                 name: str,
                 size: int,
                 data_type: str = 'int_16',
                 description: str = None,
                 optional: bool = False,
                 default: int = None,
                 value: int = None) -> None:
        """Instantiates a SignedIntField.
        
        Args:
            name: The field name must be unique within a Message.
            size: The number of *bits* used to encode the integer over-the-air
                (maximum 32).
            data_type: The integer type represented (for decoding).
            description: An optional description/purpose for the string.
            optional: Indicates if the string is optional in the Message.
            default: A default value for the string.
            value: Optional value to set during initialization.

        """
        if data_type not in ['int_8', 'int_16', 'int_32']:
            raise ValueError(f'Invalid unsignedint type {data_type}')
        if not isinstance(size, int) or size < 1:
            raise ValueError('Size must be int greater than zero')
        super().__init__(name=name,
                         data_type=data_type,
                         description=description,
                         optional=optional)
        self._size = size
        self._default = default
        self._value = value if value is not None else self._default
    
    @property
    def size(self):
        """The size of the field in bits."""
        return self._size

    @size.setter
    def size(self, value: int):
        if not isinstance(value, int) or value < 1:
            raise ValueError('Size must be integer greater than 0 bits')
        self._size = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v: int):
        clip = False
        if v is not None:
            if not isinstance(v, int):
                raise ValueError('Unsignedint must be non-negative integer')
            if v > (2**self.size / 2) - 1:
                self._value = int(2**self.size / 2) - 1
                warn(f'Clipping signedint at max value {self._value}')
                clip = True
            if v < -(2**self.size / 2):
                self._value = -1 * int(2**self.size / 2)
                warn(f'Clipping signedint at min value {self._value}')
                clip = True
        if not clip:
            self._value = v
    
    @property
    def default(self):
        """The default value."""
        return self._default
    
    @default.setter
    def default(self, v: int):
        if v is not None:
            if not isinstance(v, int):
                raise ValueError(f'Invalid signed integer {v}')
            if v > (2**self.size / 2) - 1 or v < -(2**self.size / 2):
                raise ValueError(f'Invalid default {v}')
        self._default = v
    
    @property
    def bits(self):
        """The size of the field in bits."""
        bits = self.size if self._value is not None else 0
        return bits + (1 if self.optional else 0)
    
    def encode(self) -> str:
        """Returns the binary string of the field value."""
        if self.value is None:
            raise ValueError(f'No value defined in UnsignedIntField {self.name}')
        _format = f'0{self.size}b'
        if self.value < 0:
            invertedbin = format(self.value * -1, _format)
            twocomplementbin = ''
            i = 0
            while len(twocomplementbin) < len(invertedbin):
                twocomplementbin += '1' if invertedbin[i] == '0' else '0'
                i += 1
            binstr = format(int(twocomplementbin, 2) + 1, _format)
        else:
            binstr = format(self.value, _format)
        return binstr

    def decode(self, binary_str: str) -> int:
        """Populates the field value from binary and returns the next offset.
        
        Args:
            binary_str (str): The binary string to decode
        
        Returns:
            The bit offset after parsing
        """
        value = int(binary_str[:self.size], 2)
        if (value & (1 << (self.size - 1))) != 0:   #:sign bit set e.g. 8bit: 128-255
            value = value - (1 << self.size)        #:compute negative value
        self.value = value
        return self.size

    def xml(self) -> ET.Element:
        """Returns the SignedInt XML definition for a Message Definition File.
        """
        xmlfield = self._base_xml()
        size = ET.SubElement(xmlfield, 'Size')
        size.text = str(self.size)
        if self.default:
            default = ET.SubElement(xmlfield, 'Default')
            default.text = str(self.default)
        return xmlfield
