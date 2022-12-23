from .. import ET
from .base_field import FieldCodec
from .helpers import optimal_bits


class EnumField(FieldCodec):
    """An enumerated field sends an index over-the-air representing a string."""
    def __init__(self,
                 name: str,
                 items: 'list[str]',
                 size: int,
                 description: str = None,
                 optional: bool = False,
                 default: int = None,
                 value: int = None) -> None:
        """Instantiates a EnumField.
        
        Args:
            name: The field name must be unique within a Message.
            items: A list of strings (indexed from 0).
            size: The number of *bits* used to encode the index over-the-air.
            description: An optional description/purpose for the field.
            optional: Indicates if the field is optional in the Message.
            default: A default value for the enum.
            value: Optional value to set during initialization.

        """
        super().__init__(name=name,
                         data_type='enum',
                         description=description,
                         optional=optional)
        if (not isinstance(items, list) or
            not all(isinstance(item, str) for item in items)):
            raise ValueError('Items must a list of strings')
        self._items = items
        min_size = optimal_bits((0, len(items) - 1))
        if not isinstance(size, int) or size < min_size:
            raise ValueError(f'Size must be integer greater than {min_size}')
        self._size = size
        if default is not None:
            if isinstance(default, str):
                if default not in items:
                    raise ValueError(f'{default} not found in items')
                self._default = items.index(default)
            elif isinstance(default, int):
                if default not in range(0, len(items)):
                    raise ValueError('Invalid default not in range of items')
                self._default = default
        else:
            self._default = None
        if value is not None:
            if value not in items:
                raise ValueError(f'{value} not in items')
            self._value = value
        else:
            self._value = None
    
    def _validate_enum(self, v: 'int|str') -> 'int|None':
        if v is not None:
            if isinstance(v, str):
                if v not in self.items:
                    raise ValueError(f'Invalid value {v}')
                for index, item in enumerate(self.items):
                    if item == v:
                        return index
            elif isinstance(v, int):
                if v < 0 or v >= len(self.items):
                    raise ValueError(f'Invalid enum index {v}')
            else:
                raise ValueError(f'Invalid value {v}')
        return v

    @property
    def items(self):
        return self._items
    
    @items.setter
    def items(self, l: list):
        if not isinstance(l, list) or not all(isinstance(x, str) for x in l):
            raise ValueError('Items must be a list of strings')
        self._items = l

    @property
    def default(self) -> str:
        if self._default is None:
            return None
        return self.items[self._default]
    
    @default.setter
    def default(self, v: 'int|str'):
        self._default = self._validate_enum(v)

    @property
    def value(self) -> str:
        if self._value is None:
            if self.default is not None:
                return self.default
            return None
        return self.items[self._value]
    
    @value.setter
    def value(self, v: 'int|str'):
        self._value = self._validate_enum(v)

    @property
    def size(self) -> int:
        """The size of the field in bits."""
        return self._size
    
    @size.setter
    def size(self, v: int):
        if not isinstance(v, int) or v < 1:
            raise ValueError('Size must be integer greater than zero')
        minimum_bits = optimal_bits((0, len(self.items)))
        if v < minimum_bits:
            raise ValueError(f'Size must be at least {minimum_bits}'
                             ' to support item count')
        self._size = v

    @property
    def bits(self) -> int:
        """The size of the field in bits."""
        bits = self.size if self._value is not None else 0
        return bits + (1 if self.optional else 0)
    
    def encode(self) -> str:
        """Returns the binary string of the field value."""
        if self.value is None:
            raise ValueError(f'No value configured in EnumField {self.name}')
        _format = f'0{self.bits}b'
        binstr = format(self.items.index(self.value), _format)
        return binstr

    def decode(self, binary_str: str) -> int:
        """Populates the field value from binary and returns the next offset.
        
        Args:
            binary_str (str): The binary string to decode
        
        Returns:
            The bit offset after parsing
        """
        self.value = binary_str[:self.bits]
        return self.bits

    def xml(self) -> ET.Element:
        """Returns the Enum XML definition for a Message Definition File."""
        # Size must come after Items for Inmarsat V1 parser
        xmlfield = self._base_xml()
        items = ET.SubElement(xmlfield, 'Items')
        for string in self.items:
            item = ET.SubElement(items, 'string')
            item.text = str(string)
        if self.default:
            default = ET.SubElement(xmlfield, 'Default')
            default.text = str(self.default)
        size = ET.SubElement(xmlfield, 'Size')
        size.text = str(self.size)
        return xmlfield
