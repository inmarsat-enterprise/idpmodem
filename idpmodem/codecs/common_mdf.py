"""Codec functions for IDP Common Message Format supported by Inmarsat MGS.

Also supported on ORBCOMM IGWS.

"""
import logging
import xml.etree.ElementTree as ET
from binascii import b2a_base64
from math import ceil, log2
from struct import pack, unpack
from warnings import warn
from xml.dom.minidom import parseString
from copy import deepcopy

from idpmodem.constants import DataFormat

__version__ = '2.0.0'
_log = logging.getLogger(__name__)


DATA_TYPES = {
    'bool': 'BooleanField',
    'int_8': 'SignedIntField',
    'uint_8': 'UnsignedIntField',
    'int_16': 'SignedIntField',
    'uint_16': 'UnsignedIntField',
    'int_32': 'SignedIntField',
    'uint_32': 'UnsignedIntField',
    'int_64': 'SignedIntField',
    'uint_64': 'UnsignedIntField',
    'float': 'DataField',
    'double': 'DataField',
    'string': 'StringField',
    'data': 'DataField',
    'enum': 'EnumField',
    'array': 'ArrayField',   # TODO: support for array type
}
XML_NAMESPACE = {
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    'xsd': 'http://www.w3.org/2001/XMLSchema'
}
SIN_RANGE = (16, 255)

for ns in XML_NAMESPACE:
    ET.register_namespace(ns, XML_NAMESPACE[ns])


def optimal_bits(value_range: 'tuple[int, int]') -> int:
    """Returns the optimal number of bits for encoding a specified range.
    
    Args:
        value_range: A tuple with the minimum and maximum values.
    
    Returns:
        The number of bits to optimally encode the value.
    
    Raises:
        ValueError if the 

    """
    if (not isinstance(value_range, tuple) or
        len(value_range) != 2 or
        not all(isinstance(x, int) for x in value_range) or
        value_range[0] >= value_range[1]):
        #: non-compliant
        raise ValueError('value_range must be of form (min, max)')
    total_range = value_range[1] - value_range[0]
    total_range += 1 if value_range[0] == 0 else 0
    return max(1, ceil(log2(value_range[1] - value_range[0])))


def _encode_field_length(length) -> str:
    if length < 128:
        return f'0{length:07b}'
    return f'1{length:015b}'


def _decode_field_length(binstr: str) -> 'tuple[int, int]':
    if binstr[0] == '0':
        bit_index = 8
    else:
        bit_index = 16
    length = int(binstr[1:bit_index], 2)
    return (length, bit_index)


def _attribute_equivalence(reference: object,
                           other: object,
                           exclude: "list[str]" = None) -> bool:
    for attr, val in reference.__dict__.items():
        if exclude is not None and attr in exclude:
            continue
        if not hasattr(other, attr) or val != other.__dict__[attr]:
            return False
    return True


def _indent_xml(elem: ET.Element, level=0):
    xmlstr = parseString(ET.tostring(elem)).toprettyxml(indent="  ")
    # i = "\n" + level*"  "
    # j = "\n" + (level-1)*"  "
    # if len(elem):
    #     if not elem.text or not elem.text.strip():
    #         elem.text = i + "  "
    #     if not elem.tail or not elem.tail.strip():
    #         elem.tail = i
    #     for subelem in elem:
    #         _indent_xml(subelem, level+1)
    #     if not elem.tail or not elem.tail.strip():
    #         elem.tail = j
    # else:
    #     if level and (not elem.tail or not elem.tail.strip()):
    #         elem.tail = j
    # return elem
    return xmlstr


class BaseCodec:
    def __init__(self, name: str, description: str = None) -> None:
        if not name or name.strip() == '':
            raise ValueError('Invalid name must be non-empty')
        self._name = name
        self._description = description
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    @description.setter
    def description(self, value: str):
        if value is not None and not isinstance(value, str) and not value:
            raise ValueError('Description must be non-empty string or None')
        self._description = value


class CodecList(list):
    """Base class for a specific object type list.
    
    Used for Fields, Messages, Services.

    Attributes:
        codec_cls: The object type the list is comprised of.

    """
    def __init__(self, codec_cls: object):
        super().__init__()
        self.list_type = codec_cls

    def add(self, obj: object) -> bool:
        """Add an object to the end of the list.

        Args:
            obj (object): A valid object according to the list_type
        
        Raises:
            ValueError if there is a duplicate or invalid name,
                invalid value_range or unsupported data_type
        """
        if not isinstance(obj, self.list_type):
            raise ValueError(f'Invalid {self.list_type} definition')
        for o in self:
            if o.name == obj.name:
                raise ValueError(f'Duplicate {self.list_type}'
                                 f' name {obj.name} found')
        self.append(obj)
        return True

    def __getitem__(self, n: 'str|int') -> object:
        """Retrieves an object by name or index.
        
        Args:
            n: The object name or list index
        
        Returns:
            object

        """
        if isinstance(n, str):
            for o in self:
                if o.name == n:
                    return o
            raise ValueError(f'{self.list_type} name {n} not found')
        return super().__getitem__(n)

    def __setitem__(self, n: 'str|int', value):
        if isinstance(n, str):
            for o in self:
                if o.name == n:
                    o.value = value
                    break
        else:
            super().__setitem__(n, value)

    def delete(self, name: str) -> bool:
        """Delete an object from the list by name.
        
        Args:
            name: The name of the object.

        Returns:
            boolean: success
        """
        for o in self:
            if o.name == name:
                self.remove(o)
                return True
        return False


class FieldCodec(BaseCodec):
    """The base class for a Field.
    
    Attributes:
        data_type (str): The data type from a supported list.
        name (str): The unique Field name.
        description (str): Optional description.
        optional (bool): Optional indication the field is optional.

    """
    def __init__(self,
                 name: str,
                 data_type: str,
                 description: str = None,
                 optional: bool = False) -> None:
        """Instantiates the base field.
        
        Args:
            name: The field name must be unique within a Message.
            data_type: The data type represented within the field.
            description: (Optional) Description/purpose of the field.
            optional: (Optional) Indicates if the field is mandatory.
            
        """
        super().__init__(name, description)
        if data_type not in DATA_TYPES:
            raise ValueError(f'Invalid data type {data_type}')
        self._data_type = data_type
        self._optional = optional
    
    @property
    def data_type(self) -> str:
        return self._data_type

    @property
    def optional(self) -> bool:
        return self._optional
    
    @optional.setter
    def optional(self, value: bool):
        if not value or not isinstance(value, bool):
            value = False
        self._optional = value

    @property
    def bits(self) -> int:
        """Must be subclassed."""
        raise NotImplementedError('Subclass must define bits')

    def __eq__(self, other: object) -> bool:
        """Must be subclassed.
        
        Args:
            other: The other thing being compared to this.

        """
        raise NotImplementedError('Subclass must define equivalence')

    def __repr__(self) -> str:
        rep = {}
        for name in dir(self):
            if name.startswith(('__', '_')):
                continue
            attr = getattr(self, name)
            if not callable(attr):
                rep[name] = attr
        return repr(rep)
    
    def _base_xml(self) -> ET.Element:
        """The default XML template for a Field."""
        xsi_type = DATA_TYPES[self.data_type]
        xmlfield = ET.Element('Field', attrib={
            '{http://www.w3.org/2001/XMLSchema-instance}type': xsi_type
        })
        name = ET.SubElement(xmlfield, 'Name')
        name.text = self.name
        if self.description:
            description = ET.SubElement(xmlfield, 'Description')
            description.text = str(self.description)
        if self.optional:
            optional = ET.SubElement(xmlfield, 'Optional')
            optional.text = 'true'
        return xmlfield
    
    def decode(self, *args, **kwargs):
        """Must be subclassed."""
        raise NotImplementedError('Subclass must define decode')
    
    def encode(self, *args, **kwargs):
        """Must be subclassed."""
        raise NotImplementedError('Subclass must define encode')
    
    def xml(self, *args, **kwargs):
        """Must be subclassed."""
        raise NotImplementedError('Subclass must define xml structure')
    

class Fields(CodecList):
    """The list of Fields defining a Message or ArrayElement."""
    def __init__(self, fields: 'list[FieldCodec]' = None):
        super().__init__(codec_cls=FieldCodec)
        if fields is not None:
            for field in fields:
                self.add(field)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Fields):
            return NotImplemented
        if len(self) != len(other):
            return False
        for i, field in enumerate(self):
            if field != other[i]:
                return False
        return True


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
            ota_bits += field.bits + (1 if field.optional else 0)
        return ceil(ota_bits / 8)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MessageCodec):
            return NotImplemented
        return _attribute_equivalence(self, other)

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

    def xml(self, indent: bool = False) -> ET.Element:
        """Returns the XML definition for a Message Definition File."""
        xmessage = ET.Element('Message')
        name = ET.SubElement(xmessage, 'Name')
        name.text = self.name
        min = ET.SubElement(xmessage, 'MIN')
        min.text = str(self.min)
        fields = ET.SubElement(xmessage, 'Fields')
        for field in self.fields:
            fields.append(field.xml())
        return xmessage if not indent else _indent_xml(xmessage)


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


class ServiceCodec(BaseCodec):
    """A data structure holding a set of related Forward and Return Messages.
    
    Attributes:
        name (str): The service name
        sin (int): Service Identification Number or codec service id (16..255)
        description (str): A description of the service (unsupported)
        messages_forward (list): A list of mobile-terminated Message definitions
        messages_return (list): A list of mobile-originated Message definitions

    """
    def __init__(self,
                 name: str,
                 sin: int,
                 description: str = None,
                 messages_forward: Messages = None,
                 messages_return: Messages = None) -> None:
        """Instantiates a Service made up of Messages.
        
        Args:
            name: The service name should be unique within a MessageDefinitions
            sin: The Service Identification Number (16..255)
            description: (Optional)
        """
        if not isinstance(name, str) or name == '':
            raise ValueError(f'Invalid service name {name}')
        if sin not in range(16, 256):
            raise ValueError('Invalid SIN must be 16..255')
        if description is not None:
            warn('Service Description not currently supported')
        super().__init__(name, description)
        self._sin = sin
        self._messages_forward = (messages_forward or
                                  Messages(self.sin, is_forward=True))
        self._messages_return = (messages_return or
                                 Messages(self.sin, is_forward=False))
    
    @property
    def sin(self) -> int:
        return self._sin
    
    @property
    def messages_forward(self) -> Messages:
        return self._messages_forward
    
    @messages_forward.setter
    def messages_forward(self, messages: Messages):
        if not isinstance(messages, Messages):
            raise ValueError('Invalid messages list')
        for message in messages:
            assert isinstance(message, MessageCodec)
            if not message.is_forward:
                raise ValueError(f'Message {message.name} is_forward is False')
        self._messages_forward = messages

    @property
    def messages_return(self) -> Messages:
        return self._messages_return
    
    @messages_return.setter
    def messages_return(self, messages: Messages):
        if not isinstance(messages, Messages):
            raise ValueError('Invalid messages list')
        for message in messages:
            assert isinstance(message, MessageCodec)
            if message.is_forward:
                raise ValueError(f'Message {message.name} is_forward is True')
        self._messages_return = messages
        
    def xml(self, indent: bool = False) -> ET.Element:
        """Gets the XML structure of the Service."""
        if len(self.messages_forward) == 0 and len(self.messages_return) == 0:
            raise ValueError(f'No messages defined for service {self.sin}')
        xservice = ET.Element('Service')
        name = ET.SubElement(xservice, 'Name')
        name.text = str(self.name)
        sin = ET.SubElement(xservice, 'SIN')
        sin.text = str(self.sin)
        if self.description:
            desc = ET.SubElement(xservice, 'Description')
            desc.text = str(self.description)
        if len(self.messages_forward) > 0:
            forward_messages = ET.SubElement(xservice, 'ForwardMessages')
            for m in self.messages_forward:
                forward_messages.append(m.xml())
        if len(self.messages_return) > 0:
            return_messages = ET.SubElement(xservice, 'ReturnMessages')
            for m in self.messages_return:
                return_messages.append(m.xml())
        return xservice if not indent else _indent_xml(xservice)


class Services(CodecList):
    """The list of Service(s) within a MessageDefinitions."""
    def __init__(self, services: 'list[ServiceCodec]' = None):
        super().__init__(codec_cls=ServiceCodec)
        if services is not None:
            for service in services:
                if not isinstance(service, ServiceCodec):
                    raise ValueError(f'Invalid Service {service}')
                self.add(service)
    
    def add(self, service: ServiceCodec) -> None:
        """Adds a Service to the list of Services."""
        if not isinstance(service, ServiceCodec):
            raise ValueError(f'{service} is not a valid Service')
        if service.name in self:
            raise ValueError(f'Duplicate Service {service.name}')
        for existing_service in self:
            if existing_service.sin == service.sin:
                raise ValueError(f'Duplicate SIN {service.sin}')
        self.append(service)


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
        return 1
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BooleanField):
            return NotImplemented
        return _attribute_equivalence(self, other)

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
        xmlfield = self._base_xml()
        if self.default:
            default = ET.SubElement(xmlfield, 'Default')
            default.text = 'true'
        return xmlfield


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
        if not isinstance(size, int) or size < 1:
            raise ValueError('Size must be integer greater than 0 bits')
        self._items = items
        self._size = size
        self._default = (default if default in range(0, len(self._items))
                         else None)
        self._value = value if value is not None else self._default
    
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
        return self.size
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EnumField):
            return NotImplemented
        return _attribute_equivalence(self, other)

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
        """Gets the XML structure of the EnumField."""
        xmlfield = self._base_xml()
        size = ET.SubElement(xmlfield, 'Size')
        size.text = str(self.size)
        items = ET.SubElement(xmlfield, 'Items')
        for string in self.items:
            item = ET.SubElement(items, 'string')
            item.text = str(string)
        if self.default:
            default = ET.SubElement(xmlfield, 'Default')
            default.text = str(self.default)
        return xmlfield


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
        return self.size
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UnsignedIntField):
            return NotImplemented
        return _attribute_equivalence(self, other)

    def encode(self) -> str:
        """Returns the binary string of the field value."""
        if self.value is None:
            raise ValueError(f'No value defined in UnsignedIntField {self.name}')
        _format = f'0{self.bits}b'
        return format(self.value, _format)

    def decode(self, binary_str: str) -> int:
        """Populates the field value from binary and returns the next offset.
        
        Args:
            binary_str (str): The binary string to decode
        
        Returns:
            The bit offset after parsing
        """
        self.value = int(binary_str[:self.bits], 2)
        return self.bits

    def xml(self) -> ET.Element:
        """Gets the XML structure of the UnsignedIntField."""
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
        return self.size
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SignedIntField):
            return NotImplemented
        return _attribute_equivalence(self, other)

    def encode(self) -> str:
        """Returns the binary string of the field value."""
        if self.value is None:
            raise ValueError(f'No value defined in UnsignedIntField {self.name}')
        _format = f'0{self.bits}b'
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
        value = int(binary_str[:self.bits], 2)
        if (value & (1 << (self.bits - 1))) != 0:   #:sign bit set e.g. 8bit: 128-255
            value = value - (1 << self.bits)        #:compute negative value
        self.value = value
        return self.bits

    def xml(self) -> ET.Element:
        """Gets the XML structure of the SignedIntField."""
        xmlfield = self._base_xml()
        size = ET.SubElement(xmlfield, 'Size')
        size.text = str(self.size)
        if self.default:
            default = ET.SubElement(xmlfield, 'Default')
            default.text = str(self.default)
        return xmlfield


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

    @property
    def bits(self) -> int:
        """The size of the field in bits."""
        if self.fixed or self.value is None:
            return self.size * 8
        return len(self.value) * 8
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StringField):
            return NotImplemented
        return _attribute_equivalence(self, other)

    def encode(self) -> str:
        """Returns the binary string of the field value."""
        if self.value is None and not self.optional:
            raise ValueError(f'No value defined for StringField {self.name}')
        binstr = ''.join(format(ord(c), '08b') for c in self.value)
        if self.fixed:
            binstr += ''.join('0' for bit in range(len(binstr), self.bits))
        else:
            binstr = _encode_field_length(len(self.value)) + binstr
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
            (length, bit_index) = _decode_field_length(binary_str)
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
        """Gets the XML structure of the StringField."""
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
        self._size = size
        self._default = default
        self._precision = precision
        self._value = self._default
        if value:
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
            self.fixed = True
        elif self.data_type == 'double':
            if value != 8:
                warn('Adjusting double size to 8 bytes fixed')
            self._size = 8
            self.fixed = True
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
        if not self.data_type in ('float', 'double'):
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
        self._default = self._validate_data(v)

    @property
    def precision(self) -> 'int|None':
        """The number of decimal places for `float` or `double` data types."""
        return self._precision

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
            return 0
        return len(self._value) * 8
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DataField):
            return NotImplemented
        return _attribute_equivalence(self, other)

    def encode(self) -> str:
        """Returns the binary string of the field value."""
        if self.value is None and not self.optional:
            raise ValueError(f'No value defined for DataField {self.name}')
        binstr = ''
        binstr = ''.join(format(b, '08b') for b in self._value)
        if self.fixed:   #:pad to fixed length
            binstr += ''.join('0' for bit in range(len(binstr), self.bits))
        else:
            binstr = _encode_field_length(len(self._value)) + binstr
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
            (length, bit_index) = _decode_field_length(binary_str)
            binary = binary_str[bit_index:length * 8 + bit_index]
            bits = len(binary)
        self._value = int(binary, 2).to_bytes(int(bits / 8), 'big')
        return self.bits

    def xml(self) -> ET.Element:
        """The XML structure of the DataField."""
        xmlfield = self._base_xml()
        size = ET.SubElement(xmlfield, 'Size')
        size.text = str(self.size)
        if self.default:
            default = ET.SubElement(xmlfield, 'Default')
            default.text = str(self.default)
        return xmlfield


class ArrayField(FieldCodec):
    """An Array Field provides a list where each element is a set of Fields.
    
    Attributes:
        name (str): The name of the field instance.
        size (int): The maximum number of elements allowed.
        fields (Fields): A list of Field types comprising each ArrayElement
        description (str): An optional description of the array/use.
        optional (bool): Indicates if the array is optional in the Message
        fixed (bool): Indicates if the array is always the fixed `size`
        elements (list): The enumerated list of ArrayElements

    """
    def __init__(self,
                 name: str,
                 size: int,
                 fields: Fields,
                 description: str = None,
                 optional: bool = False,
                 fixed: bool = False,
                 elements: 'list[Fields]' = []) -> None:
        """Initializes an ArrayField instance.
        
        Args:
            name: The unique field name within the Message.
            size: The maximum number of elements allowed.
            fields: The list of Field types comprising each element.
            description: An optional description/purpose of the array.
            optional: Indicates if the array is optional in the Message.
            fixed: Indicates if the array is always the fixed `size`.
            elements: Option to populate elements of Fields during instantiation.

        """
        super().__init__(name=name,
                         data_type='array',
                         description=description,
                         optional=optional)
        self._size = size
        self._fixed = fixed
        self._fields = fields
        self._elements = elements or []
    
    @property
    def size(self) -> int:
        """The maximum number of array elements."""
        return self._size
    
    @size.setter
    def size(self, value: int):
        if not isinstance(value, int) or value < 1:
            raise ValueError('Size must be integer greater than 0')
        self._size = value
    
    @property
    def fixed(self) -> bool:
        """Indicates if the array is a fixed size (padded with defaults)."""
        return self._fixed

    @property
    def fields(self) -> Fields:
        """The set of `FieldCodec`s that make up each array element."""
        return self._fields

    @fields.setter
    def fields(self, fields: Fields):
        if not isinstance(fields, Fields):
            raise ValueError('Invalid Fields definition for ArrayField')
        self._fields = fields

    @property
    def elements(self) -> 'list[Fields]':
        """The list of elements (field sets) in the array."""
        return self._elements
    
    @elements.setter
    def elements(self, elements: 'list[Fields]'):
        if (not isinstance(elements, list) or 
            not all(isinstance(item, Fields) for item in elements)):
            raise ValueError('Elements must be a list of grouped Fields')
        for fields in elements:
            # assert isinstance(fields, Fields)
            for index, field in enumerate(fields):
                assert isinstance(field, FieldCodec)
                if (field.name != self.fields[index].name):
                    raise ValueError(f'fields[{index}].name'
                                     f' expected {self.fields[index].name}'
                                     f' got {field.name}')
                if (field.data_type != self.fields[index].data_type):
                    raise ValueError(f'fields[{index}].data_type'
                                     f' expected {self.fields[index].data_type}'
                                     f' got {field.data_type}')
                #TODO: validate non-optional fields have value/elements
                if (not field.optional and
                    not isinstance(field, ArrayField) and
                    field.value is None):
                    raise ValueError(f'fields[{index}].value missing')
                try:
                    self._elements[index] = fields
                except IndexError:
                    self._elements.append(fields)

    @property
    def bits(self) -> int:
        """The size of the array in bits."""
        bits = 0
        for field in self.fields:
            # assert isinstance(field, FieldCodec)
            bits += field.bits
        return bits
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ArrayField):
            return NotImplemented
        return _attribute_equivalence(self, other)

    def _valid_element(self, element: Fields) -> bool:
        for i, field in enumerate(self.fields):
            # assert isinstance(field, FieldCodec)
            e_field = element[i]
            # assert isinstance(e_field, FieldCodec)
            if e_field.name != field.name:
                raise ValueError(f'element field name {e_field.name}'
                                 f' does not match {field.name}')
            if e_field.data_type != field.data_type:
                raise ValueError(f'element field data_type {e_field.data_type}'
                                 f' does not match {field.data_type}')
            if e_field.optional != field.optional:
                raise ValueError(f'element optional {e_field.optional}'
                                 f' does not match {field.optional}')
            if (hasattr(field, 'fixed') and
                hasattr(e_field, 'fixed') and
                e_field.fixed != field.fixed):
                raise ValueError(f'element fixed {e_field.fixed}'
                                 f' does not match {field.fixed}')
            if (hasattr(field, 'size') and
                hasattr(e_field, 'size') and
                e_field.size != field.size):
                raise ValueError(f'element size {e_field.size}'
                                 f' does not match {field.size}')
        return True

    def _append(self, element: Fields):
        """Adds the array element to the list of elements."""
        if not isinstance(element, Fields):
            raise ValueError('Invalid element definition must be Fields')
        if self._valid_element(element):
            for i, field in enumerate(element):
                assert isinstance(field, FieldCodec)
                if (hasattr(field, 'description') and
                    field.description != self.fields[i].description):
                    element[i].description = self.fields[i].description
                if hasattr(field, 'value') and field.value is None:
                    element[i].value = self.fields[i].default
            self._elements.append(element)

    def new_element(self) -> Fields:
        """Returns an empty element at the end of the elements list."""
        new_index = len(self._elements)
        new_fields = deepcopy(self.fields)
        self._append(Fields(new_fields))
        return self.elements[new_index]

    def encode(self) -> str:
        """Returns the binary string of the field value."""
        if len(self.elements) == 0:
            raise ValueError('No elements to encode')
        binstr = ''
        for element in self.elements:
            for field in element:
                binstr += field.encode()
        if not self.fixed:
            binstr = _encode_field_length(len(self.elements)) + binstr
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
            (length, bit_index) = _decode_field_length(binary_str)
        for index in range(0, length):
            fields = Fields(self.fields)
            for field in fields:
                if field.optional:
                    if binary_str[bit_index] == '0':
                        bit_index += 1
                        continue
                    bit_index += 1
                bit_index += field.decode(binary_str[bit_index:])
            try:
                self._elements[index] = fields
            except IndexError:
                self._elements.append(fields)
        return bit_index

    def xml(self) -> ET.Element:
        """The XML representation of the ArrayField."""
        xmlfield = self._base_xml()
        size = ET.SubElement(xmlfield, 'Size')
        size.text = str(self.size)
        if self.fixed:
            default = ET.SubElement(xmlfield, 'Fixed')
            default.text = 'true'
        fields = ET.SubElement(xmlfield, 'Fields')
        for field in self.fields:
            # assert isinstance(field, FieldCodec)
            fields.append(field.xml())
        return xmlfield


class MessageDefinitions:
    """A set of Message Definitions grouped into Services.

    Attributes:
        services: The list of Services with Messages defined.
    
    """
    def __init__(self, services: Services = None):
        if services is not None:
            if not isinstance(services, Services):
                raise ValueError('Invalid Services')
        self.services = services or Services()
    
    def xml(self, indent: bool = False) -> ET.Element:
        """Gets the XML structure of the complete message definitions.
        
        Args:
            indent: If `True` each layer of the XML will indent 2 spaces.

        """
        xmsgdef = ET.Element('MessageDefinition',
                             attrib={'xmlns:xsd': XML_NAMESPACE['xsd']})
        services = ET.SubElement(xmsgdef, 'Services')
        for service in self.services:
            # assert isinstance(service, ServiceCodec)
            services.append(service.xml())
        return xmsgdef if not indent else _indent_xml(xmsgdef)
    
    def mdf_export(self, filename: str, pretty: bool = False):
        """Creates an XML file at the target location.
        
        Args:
            filename: The full path/filename to save to. `.idpmsg` is
                recommended as a file extension.
            pretty: If `True` will indent each layer of the XML by 2 spaces.

        """
        tree = ET.ElementTree(self.xml())
        root = tree.getroot()
        if pretty:
            from xml.dom.minidom import parseString
            xmlstr = parseString(ET.tostring(root)).toprettyxml(indent="  ")
            with open(filename, 'w') as f:
                f.write(xmlstr)
        else:
            with open(filename, 'wb') as f:
                tree.write(f, encoding='utf-8', xml_declaration=True)
