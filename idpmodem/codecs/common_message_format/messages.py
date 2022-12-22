import math
from binascii import b2a_base64

from . import ET
from .base import BaseCodec, CodecList
from .fields.base_field import FieldCodec, Fields

from idpmodem.constants import DataFormat


class MessageCodec(BaseCodec):
    """The Payload structure for Message Definition Files uploaded to a Mailbox.
    
    Attributes:
        name (str): The message name
        sin (int): The Service Identification Number
        min (int): The Message Identification Number
        fields (list): A list of Fields
        description (str): Optional description
        is_forward (bool): Indicates if the message is mobile-terminated

    """

    def __init__(self,
                 name: str,
                 sin: int,
                 min: int,
                 description: str = None,
                 is_forward: bool = False,
                 fields: Fields = None):
        """Instantiates a Message.
        
        Args:
            name: The message name should be unique within the xMessages list.
            sin: The Service Identification Number (16..255)
            min: The Message Identification Number (0..255)
            description: (Optional) Description/purpose of the Message.
            is_forward: Indicates if the message is intended to be
                Mobile-Terminated.
            fields: Optional definition of fields during instantiation.

        """
        if not isinstance(sin, int) or sin not in range(16, 256):
            raise ValueError(f'Invalid SIN {sin} must be in range 16..255')
        if not isinstance(min, int) or min not in range (0, 256):
            raise ValueError(f'Invalid MIN {min} must be in range 0..255')
        super().__init__(name, description)
        self._is_forward = is_forward
        self._sin = sin
        self._min = min
        self._fields: Fields = fields or Fields()

    @property
    def is_forward(self) -> bool:
        return self._is_forward
    
    @property
    def sin(self) -> int:
        return self._sin

    @property
    def min(self) -> int:
        return self._min

    @property
    def fields(self) -> Fields:
        return self._fields
    
    @fields.setter
    def fields(self, fields: Fields):
        if not all(isinstance(field, FieldCodec) for field in fields):
            raise ValueError('Invalid field found in list')
        self._fields = fields

    @property
    def ota_size(self) -> int:
        ota_bits = 2 * 8
        for field in self.fields:
            assert isinstance(field, FieldCodec)
            ota_bits += field.bits
        return math.ceil(ota_bits / 8)

    def decode(self, databytes: bytes) -> None:
        """Parses and stores field values from raw data (received over-the-air).
        
        Args:
            databytes: A bytes array (typically from the forward message)
        """
        binary_str = ''.join(format(int(b), '08b') for b in databytes)
        bit_offset = 16   #: Begin after SIN/MIN bytes
        for field in self.fields:
            assert isinstance(field, FieldCodec)
            if field.optional:
                present = binary_str[bit_offset] == '1'
                bit_offset += 1
                if not present:
                    continue
            bit_offset += field.decode(binary_str[bit_offset:])

    def encode(self,
               data_format: int = DataFormat.BASE64,
               exclude: list = None) -> dict:
        """Encodes using the specified data format (base64 or hex).

        Args:
            data_format (int): 2=ASCII-Hex, 3=base64
            exclude (list[str]): A list of optional field names to exclude
        
        Returns:
            Dictionary with sin, min, data_format and data to pass into AT%MGRT
                or atcommand function `message_mo_send`
        """
        if data_format not in [DataFormat.BASE64, DataFormat.HEX]:
            raise ValueError(f'data_format {data_format} unsupported')
        bin_str = ''
        for field in self.fields:
            assert isinstance(field, FieldCodec)
            if field.optional:
                if exclude is not None and field.name in exclude:
                    present = False
                elif hasattr(field, 'value'):
                    present = field.value is not None
                elif hasattr(field, 'elements'):
                    present = field.elements is not None
                else:
                    raise ValueError('Unknown value of optional')
                bin_str += '1' if present else '0'
                if not present:
                    continue
            bin_str += field.encode()
        for _ in range(0, 8 - len(bin_str) % 8):   #:pad to next byte
            bin_str += '0'
        _format = f'0{int(len(bin_str) / 8 * 2)}X'   #:hex bytes 2 chars
        hex_str = format(int(bin_str, 2), _format)
        if (self.is_forward and len(hex_str) / 2 > 9998 or
            not self.is_forward and len(hex_str) / 2 > 6398):
            raise ValueError(f'{len(hex_str) / 2} bytes exceeds maximum size'
                             ' for Payload')
        if data_format == DataFormat.HEX:
            data = hex_str
        else:
            data = b2a_base64(bytearray.fromhex(hex_str)).strip().decode()
        return {
            'sin': self.sin,
            'min': self.min,
            'data_format': data_format,
            'data': data
        }

    def xml(self) -> ET.Element:
        """Returns the Message XML definition for a Message Definition File."""
        xmessage = ET.Element('Message')
        name = ET.SubElement(xmessage, 'Name')
        name.text = self.name
        min = ET.SubElement(xmessage, 'MIN')
        min.text = str(self.min)
        fields = ET.SubElement(xmessage, 'Fields')
        for field in self.fields:
            fields.append(field.xml())
        return xmessage


class Messages(CodecList):
    """The list of Messages (Forward or Return) within a Service."""
    def __init__(self, sin: int, is_forward: bool):
        super().__init__(codec_cls=MessageCodec)
        self.sin = sin
        self.is_forward = is_forward
    
    def add(self, message: MessageCodec) -> None:
        """Add a message to the list if it matches the parent SIN.

        Overrides the base class add method.

        Args:
            message (object): A valid Message
        
        Raises:
            ValueError if there is a duplicate or invalid name,
                invalid value_range or unsupported data_type

        """
        if not isinstance(message, MessageCodec):
            raise ValueError('Invalid message definition')
        if message.sin != self.sin:
            raise ValueError(f'Message SIN {message.sin} does not match'
                             f' service {self.sin}')
        for m in self:
            assert isinstance(m, MessageCodec)
            if m.name == message.name:
                raise ValueError(f'Duplicate message name {message.name} found')
            if m.min == message.min:
                raise ValueError(f'Duplicate message MIN {message.min} found')
        self.append(message)
