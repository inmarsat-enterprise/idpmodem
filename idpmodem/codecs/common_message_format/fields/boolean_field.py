from .. import ET
from .base_field import FieldCodec


class BooleanField(FieldCodec):
    """A Boolean field."""
    def __init__(self,
                 name: str,
                 description: str = None,
                 optional: bool = False,
                 default: bool = False,
                 value: bool = None) -> None:
        super().__init__(name=name,
                         data_type='bool',
                         description=description,
                         optional=optional)
        """Instantiates a BooleanField.
        
        Args:
            name: The field name must be unique within a Message.
            description: An optional description/purpose for the field.
            optional: Indicates if the field is optional in the Message.
            default: A default value for the boolean.
            value: Optional value to set during initialization.

        """
        self._default = default if isinstance(default, bool) else False
        self._value = value if value is not None else self._default
    
    @property
    def default(self):
        return self._default

    @default.setter
    def default(self, v: bool):
        if v is not None and not isinstance(v, bool):
            raise ValueError(f'Invalid boolean value {v}')
        self._default = v

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v: bool):
        if v is not None and not isinstance(v, bool):
            raise ValueError(f'Invalid boolean value {v}')
        self._value = v

    @property
    def bits(self):
        return 1 + (1 if self.optional else 0)
    
    def encode(self) -> str:
        """Returns the binary string of the field value."""
        if self.value is None and not self.optional:
            raise ValueError('No value assigned to field')
        return '1' if self.value else '0'

    def decode(self, binary_str: str) -> int:
        """Populates the field value from binary and returns the next offset.
        
        Args:
            binary_str (str): The binary string to decode
        
        Returns:
            The bit offset after parsing
        """
        self.value = True if binary_str[0] == '1' else False
        return 1

    def xml(self) -> ET.Element:
        """Returns the Boolean XML definition for a Message Definition File."""
        xmlfield = self._base_xml()
        if self.default:
            default = ET.SubElement(xmlfield, 'Default')
            default.text = 'true'
        return xmlfield
