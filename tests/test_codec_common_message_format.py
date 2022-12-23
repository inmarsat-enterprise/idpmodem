import logging
import base64
import json
import os
import math
import xml.etree.ElementTree as ET
from copy import deepcopy

import pytest
from idpmodem.codecs.common_message_format import *
from idpmodem.codecs.common_message_format.fields.helpers import optimal_bits
from idpmodem.codecs.common_message_format.message_definitions import _indent
from idpmodem.constants import DataFormat
from idpmodem.location import Location

logging.basicConfig()
logger = logging.getLogger()


@pytest.fixture
def bool_field() -> BooleanField:
    """Returns a BooleanField."""
    def _bool_field(name: str = 'boolFixture',
                    optional: bool = False,
                    default: bool = False,
                    value: bool = None):
        return BooleanField(name=name,
                            optional=optional,
                            default=default,
                            value=value,
                            description='A boolean test field.')
    return _bool_field


@pytest.fixture
def data_field_data() -> DataField:
    """Returns a DataField with no value."""
    def _data_field(size: int = 1,
                    data_type: str = 'data',
                    optional: bool = False,
                    fixed: bool = False,
                    default: bytes = None,
                    value: bytes = None):
        return DataField(name='dataFixture',
                        size=size,
                        data_type=data_type,
                        optional=optional,
                        fixed=fixed,
                        default=default,
                        value=value,
                        description='A data test field.')
    return _data_field


@pytest.fixture
def data_field_float() -> DataField:
    """Returns a DataField float with no value."""
    def _data_field(size: int = 4,
                    data_type: str = 'float',
                    precision: int = None,
                    optional: bool = False,
                    fixed: bool = False,
                    default: bytes = None,
                    value: float = None):
        return DataField(name='dataFixture',
                        size=size,
                        data_type=data_type,
                        precision=precision,
                        optional=optional,
                        fixed=fixed,
                        default=default,
                        value=value,
                        description='A float test field.')
    return _data_field


@pytest.fixture
def data_field_double() -> DataField:
    """Returns a DataField double float with no value."""
    def _data_field(size: int = 8,
                    data_type: str = 'double',
                    precision: int = None,
                    optional: bool = False,
                    fixed: bool = False,
                    default: bytes = None,
                    value: float = None):
        return DataField(name='dataFixture',
                        size=size,
                        data_type=data_type,
                        precision=precision,
                        optional=optional,
                        fixed=fixed,
                        default=default,
                        value=value,
                        description='A double float test field.')
    return _data_field


@pytest.fixture
def enum_field() -> EnumField:
    """Returns a EnumField with no value."""
    fixture_items = ['item1', 'item2', 'item3']
    def _enum_field(name: str = 'enumFixture',
                    items: list = fixture_items,
                    size: int = 2,
                    description: str = 'An enum test field'):
        return EnumField(name=name,
                        items=items,
                        size=size,
                        description=description)
    return _enum_field


@pytest.fixture
def int_field() -> SignedIntField:
    def _int_field(name: str = 'signedintField',
                   size: int = 16,
                   data_type: str = 'int_16',
                   description: str = 'A signedint field'):
        return SignedIntField(name=name,
                            size=size,
                            data_type=data_type,
                            description=description)
    return _int_field


@pytest.fixture
def uint_field() -> UnsignedIntField:
    def _uint_field(name: str = 'signedintField',
                   size: int = 16,
                   data_type: str = 'int_16',
                   description: str = 'A signedint field'):
        return UnsignedIntField(name=name,
                                size=size,
                                data_type=data_type,
                                description=description)
    return _uint_field


@pytest.fixture
def string_field() -> StringField:
    """Returns a fixed StringField 10 characters long."""
    def _string_field(name: str = 'stringFixture',
                      size: int = 200,
                      fixed: bool = False,
                      optional: bool = False,
                      default: str = None,
                      value: str = None):
        return StringField(name=name,
                        description='A fixed string test field.',
                        fixed=fixed,
                        size=size,
                        optional=optional,
                        default=default,
                        value=value)
    return _string_field


@pytest.fixture
def array_element_fields_example() -> Fields:
    fields = Fields()
    fields.add(StringField(name='propertyName', size=50))
    fields.add(UnsignedIntField(name='propertyValue',
                                size=32,
                                data_type='uint_32'))
    return fields


@pytest.fixture
def array_field(array_element_fields_example) -> ArrayField:
    """Returns a ArrayField defaulting to array_element_fields_example."""
    def _array_field(name: str = 'arrayFixture',
                     size: int = 1,
                     fields: Fields = None,
                     description: str = 'An example array',
                     optional: bool = False,
                     fixed: bool = False,
                     elements: 'list[Fields]' = []):
        return ArrayField(name=name,
                        description=description,
                        size=size,
                        fields=fields or array_element_fields_example,
                        optional=optional,
                        fixed=fixed,
                        elements=elements)
    return _array_field


@pytest.fixture
def return_message(array_element_fields_example) -> MessageCodec:
    """Returns a ArrayField with no values."""
    fields = Fields()
    fields.add(BooleanField(name='testBool', value=True))
    fields.add(UnsignedIntField(name='testUint',
                                size=16,
                                data_type='uint_16',
                                value=42))
    fields.add(SignedIntField(name='latitude',
                            size=24,
                            data_type='int_32',
                            value=int(-45.123 * 60000)))
    fields.add(StringField(name='optionalString',
                        size=100,
                        optional=True))
    fields.add(StringField(name='nonOptionalString',
                        size=100,
                        value='A quick brown fox'))
    fields.add(ArrayField(name='arrayExample',
                          size=50,
                          fields=array_element_fields_example))
    array_field: ArrayField = fields['arrayExample']
    element_one = array_element_fields_example
    element_one['propertyName'].value = 'aPropertyName'
    element_one['propertyValue'].value = 1
    array_field.append(element_one)
    element_two = array_element_fields_example
    element_two['propertyName'].value = 'anotherPropertyName'
    element_two['propertyValue'].value = 42
    array_field.append(element_two)
    fields.add(DataField(name='testData',
                        size=4,
                        data_type='float',
                        value=4.2,
                        precision=2))
    message = MessageCodec(name='returnMessageFixture',
                        sin=255,
                        min=1,
                        fields=fields)
    return message


@pytest.fixture
def return_message_optional_field() -> MessageCodec:
    """"""
    fields = Fields()
    fields.add(StringField(name='optionalString',
                        size=100,
                        optional=True))
    message = MessageCodec(name='returnMessageFixture',
                        sin=255,
                        min=1,
                        fields=fields)
    return message


@pytest.fixture
def return_messages(return_message) -> Messages:
    return_messages = Messages(sin=255, is_forward=False)
    return_messages.add(return_message)
    return return_messages


@pytest.fixture
def service(return_messages) -> ServiceCodec:
    service = ServiceCodec(name='testService', sin=255, description='A test service')
    service.messages_return = return_messages
    return service


@pytest.fixture
def services(service) -> Services:
    services = Services()
    services.add(service)
    return services


@pytest.fixture
def message_definitions(services) -> MessageDefinitions:
    message_definitions = MessageDefinitions()
    message_definitions.services = services
    return message_definitions


def test_boolean_field(bool_field):
    test_field: BooleanField = bool_field()
    assert(not test_field.value)
    assert(not test_field.optional)
    assert(not test_field.default)
    assert(test_field.encode() == '0')
    test_field.value = False
    assert(not test_field.value)
    with pytest.raises(ValueError):
        test_field.value = 1
    bool_dflt_true: BooleanField = bool_field(default=True)
    assert(bool_dflt_true.encode() == '1')
    bool_dflt_false_valset: BooleanField = bool_field(value=True)
    assert(bool_dflt_false_valset.encode() == '1')


def test_data_field_data(data_field_data: DataField):
    MAX_BYTES = 128
    test_field: DataField = data_field_data(size=MAX_BYTES)
    assert(not test_field.value)
    assert(not test_field.optional)
    assert(not test_field.default)
    with pytest.raises(ValueError):
        test_field.encode()
    for i in range(0, MAX_BYTES):
        b = [i % 255] * max(1, i)
        test_field.value = bytes(b)
        enc = test_field.encode()
        bits = len(enc)
        L = enc[:16] if i > 127 else enc[:8]
        data_bin = enc[len(L):]
        data_length = int(L[1:], 2)
        assert(data_length == len(b))
        data_bin = enc[len(L):]
        data = int(data_bin, 2).to_bytes(int((bits - len(L)) / 8), 'big')
        assert(data == bytes(b))
        test_field.value = None
        assert(test_field.value is None)
        test_field.decode(enc)
        assert(test_field.value == bytes(b))
    #TODO: test cases for padding, truncation


def test_data_field_float(data_field_float: DataField):
    test_value = 1.234567
    precision = 6
    test_field: DataField = data_field_float(precision=precision,
                                             value=test_value)
    assert test_field.size == 4
    assert test_field.fixed == True
    assert len(test_field.value) == 4
    assert test_field.precision == precision
    assert test_field.converted_value == test_value


def test_data_field_double(data_field_double: DataField):
    test_value = 1.7976931348623158e+308
    precision = None
    test_field: DataField = data_field_double(precision=precision,
                                              value=test_value)
    assert test_field.size == 8
    assert test_field.fixed
    assert len(test_field.value) == 8
    assert test_field.precision == precision
    assert test_field.converted_value == test_value


def test_string_field(string_field):
    from string import ascii_lowercase as char_iterator
    MAX_SIZE = 155
    FIXED_SIZE = 6
    FIXED_STR_LONG = 'abcdefghi'
    FIXED_STR_SHORT = 'a'
    test_field: StringField = string_field(size=MAX_SIZE)
    assert(not test_field.value)
    assert(not test_field.optional)
    assert(not test_field.default)
    with pytest.raises(ValueError):
        test_field.encode()
    test_str = ''
    for i in range(0, MAX_SIZE):
        if i > test_field.size:
            break
        test_str += char_iterator[i % 26]
        test_field.value = test_str
        binstr = ''.join(format(ord(c), '08b') for c in test_str)
        enc = test_field.encode()
        L = enc[:16] if len(test_str) > 127 else enc[:8]
        assert(enc == L + binstr)
        test_field.value = None
        assert(test_field.value is None)
        test_field.decode(enc)
        assert(test_field.value == test_str)
    test_field = string_field(size=FIXED_SIZE)
    test_field.value = FIXED_STR_LONG
    assert(test_field.value == FIXED_STR_LONG[:FIXED_SIZE])
    test_field.fixed = True
    test_field.value = FIXED_STR_SHORT
    assert(test_field.value == FIXED_STR_SHORT)
    binstr = ''.join(format(ord(c), '08b') for c in FIXED_STR_SHORT)
    binstr += '0' * 8 * (FIXED_SIZE - len(FIXED_STR_SHORT))
    enc = test_field.encode()
    assert(len(enc) == FIXED_SIZE * 8)
    assert(enc == binstr)
    v = test_field.value
    test_field.decode(enc)
    assert(test_field.value == v)


def test_encode_optional(return_message_optional_field):
    TEST_STR = 'optional'
    SIN_MIN = 2 * 8
    OPT = 1
    L = 8 if len(TEST_STR) < 128 else 16
    ASCII = len(TEST_STR) * 8
    rm: MessageCodec = return_message_optional_field
    rm.fields['optionalString'].value = TEST_STR
    PRESENT_BYTES = math.ceil((SIN_MIN + OPT + L + ASCII) / 8)
    assert rm.ota_size == PRESENT_BYTES
    present = rm.encode()
    assert len(base64.b64decode(present['data'])) == PRESENT_BYTES - 2
    rm.fields['optionalString'].value = None
    NOTPRESENT_BYTES = math.ceil((SIN_MIN + OPT) / 8)
    assert rm.ota_size == NOTPRESENT_BYTES
    notpresent = rm.encode()
    assert len(base64.b64decode(notpresent['data'])) == NOTPRESENT_BYTES - 2


def test_array_field(array_field, array_element_fields_example):
    MAX_SIZE = 10
    test_field: ArrayField = array_field(size=MAX_SIZE,
                                         fields=array_element_fields_example)
    assert(not test_field.fixed)
    assert(not test_field.optional)
    with pytest.raises(ValueError):
        test_field.encode()
    for i in range(0, MAX_SIZE):
        element = array_element_fields_example
        element['propertyName'] = f'testProp{i}'
        element['propertyValue'] = i
        test_field.append(element)
        ref = deepcopy(test_field)
        enc = test_field.encode()
        L = enc[:16] if i > 127 else enc[:8]
        assert(len(test_field.elements) == int('0b' + L, 2))
        test_field.decode(enc)
        assert(test_field == ref)


def test_optimal_bits():
    with pytest.raises(ValueError):
        optimal_bits(1)
    with pytest.raises(ValueError):
        optimal_bits((1))
    with pytest.raises(ValueError):
        optimal_bits((1, 0))
    test_range_1 = (0, 1)
    assert optimal_bits(test_range_1) == 1
    test_range_2 = (0, 2)
    assert optimal_bits(test_range_2) == 2
    test_range_3 = (-90 * 60 * 1000, 90 * 60 * 1000)
    assert optimal_bits(test_range_3) == 24
    test_range_4 = (-180 * 60 * 1000, 180 * 60 * 1000)
    assert optimal_bits(test_range_4) == 25


def test_enum_field():
    test_items = ['item1', 'item2', 'item3']
    size = 2
    defaults = [None, 'item1', 1]
    for test_default in defaults:
        test_field = EnumField(name='validEnum',
                               items=test_items,
                               size=size,
                               default=test_default)
        assert(test_field.items == test_items)
        if test_default is None:
            assert(test_field.value is None)
        elif isinstance(test_default, str):
            assert(test_field.value == test_default)
        else:
            assert(test_field.value == test_items[test_default])
    assert(test_field.encode() == '01')  #:assumes last default is 1
    with pytest.raises(ValueError):
        test_field = EnumField(name='testEnum', items=None, size=None)
    with pytest.raises(ValueError):
        test_field = EnumField(name='testEnum', items=[1, 3], size=2)
    with pytest.raises(ValueError):
        test_field = EnumField(name='testEnum', items=test_items, size=1)


@pytest.mark.filterwarnings('ignore:Clipping')
def test_unsignedint_field():
    BIT_SIZE = 16
    with pytest.raises(ValueError):
        test_field = UnsignedIntField(name='failedBitSize', size=0)
    test_field = UnsignedIntField(name='testUint', size=BIT_SIZE)
    assert(test_field.default is None)
    assert(test_field.value is None)
    with pytest.raises(ValueError):
        test_field.encode()
    with pytest.raises(ValueError):
        test_field.value = -1
    test_field.value = 1
    assert(test_field.encode() == '0' * (BIT_SIZE - 1) + '1')
    test_field.value = 2**BIT_SIZE
    assert(test_field.value == 2**BIT_SIZE - 1)
    v = test_field.value
    enc = test_field.encode()
    assert(len(enc) == BIT_SIZE)
    test_field.decode(enc)
    assert(test_field.value == v)


@pytest.mark.filterwarnings('ignore:Clipping')
def test_signedint_field():
    BIT_SIZE = 16
    with pytest.raises(ValueError):
        test_field = SignedIntField(name='failedBitSize', size=0)
    test_field = SignedIntField(name='testInt', size=BIT_SIZE)
    assert(test_field.default is None)
    assert(test_field.value is None)
    with pytest.raises(ValueError):
        test_field.encode()
    test_field.value = -1
    assert(test_field.encode() == '1' * BIT_SIZE)
    test_field.value = 2**BIT_SIZE
    assert(test_field.value == 2**BIT_SIZE / 2 - 1)
    v = test_field.value
    enc = test_field.encode()
    assert(len(enc) == BIT_SIZE)
    test_field.decode(enc)
    assert(test_field.value == v)
    test_field.value = -(2**BIT_SIZE)
    assert(test_field.value == -(2**BIT_SIZE / 2))
    v = test_field.value
    enc = test_field.encode()
    assert(len(enc) == BIT_SIZE)
    test_field.decode(enc)
    assert(test_field.value == v)


def test_bool_xml(bool_field):
    test_field = bool_field()
    xml = test_field.xml()
    assert(xml.attrib['{http://www.w3.org/2001/XMLSchema-instance}type'] == 'BooleanField')
    assert(xml.find('Name').text == test_field.name)
    assert(xml.find('Description').text == test_field.description)


def test_enum_xml(enum_field):
    test_field: EnumField = enum_field()
    xml: ET.Element = test_field.xml()
    assert(xml.attrib['{http://www.w3.org/2001/XMLSchema-instance}type'] == 'EnumField')
    assert(xml.find('Name').text == test_field.name)
    assert(xml.find('Description').text == test_field.description)
    items = xml.find('Items')
    i = 0
    for item in items.findall('string'):
        string = item.text
        assert(string == test_field.items[i])
        i += 1
    assert(xml.find('Size').text == str(test_field.size))
    # Ensure Size follows Items for Inmarsat API V1
    tree = ET.ElementTree(xml)
    root = tree.getroot()
    enum_str: str = ET.tostring(root).decode('utf8')
    assert enum_str.find('<Items>') < enum_str.find('<Size>')


def test_indent():
    root = ET.fromstring('<A><B>..</B><C><D>...</D></C></A>')
    spaces = 2
    _indent(root, spaces=spaces)
    output = ET.tostring(root).decode('utf-8')
    test_filename = './temp/indent.xml'
    with open(test_filename, 'w') as f:
        f.write(output)
    with open(test_filename, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if any(x in line for x in ['<A>', '</A>']):
                assert line.startswith('<')
            elif any(x in line for x in ['<B>', '</B>', '<C>', '</C>']):
                assert line.startswith(' ' * spaces + '<')
            elif any(x in line for x in ['<D>', '</D>']):
                assert line.startswith(' ' * spaces * 2 + '<')
    os.remove(test_filename)


def test_array_xml(array_field):
    test_field: ArrayField = array_field()
    xml = test_field.xml()
    assert(xml.attrib['{http://www.w3.org/2001/XMLSchema-instance}type'] == 'ArrayField')
    assert(xml.find('Name').text == test_field.name)
    assert(xml.find('Size').text == str(test_field.size))
    assert(xml.find('Description').text == test_field.description)
    i = 0
    fields = xml.find('Fields')
    for field in fields.findall('Field'):
        assert(field.find('Name').text == test_field.fields[i].name)
        i += 1
    # Ensure Size follows Fields for Inmarsat API V1
    tree = ET.ElementTree(xml)
    root = tree.getroot()
    enum_str: str = ET.tostring(root).decode('utf8')
    assert enum_str.find('<Fields>') < enum_str.find('<Size>')


def test_return_message_xml(return_message):
    rm: MessageCodec = return_message
    xml = rm.xml()
    assert xml.find('Name').text == rm.name
    assert int(xml.find('MIN').text) == rm.min
    assert xml.find('Fields')


def test_mdf_xml(message_definitions: MessageDefinitions):
    test_filename = './temp/mdf.xml'
    message_definitions.mdf_export(test_filename, pretty=True)
    assert True   # manual validation


def test_rm_codec(return_message):
    msg: MessageCodec = return_message
    msg_copy = deepcopy(return_message)
    encoded = msg.encode(data_format=DataFormat.HEX)
    hex_message = (format(encoded['sin'], '02X') +
                   format(encoded['min'], '02X') +
                   encoded['data'])
    msg.decode(bytes.fromhex(hex_message))
    assert(msg_copy == msg)


HELP_CODES = ['FIRE', 'MEDICAL']
class TextMo(MessageCodec):
    """A Mobile-Originated text message sent device-to-cloud."""
    def __init__(self, **kwargs):
        name = 'textMobileOriginated'
        msg_desc = ('Sends a text or message code, with optional location'
                    ' and destination address.')
        super().__init__(name=name,
                         description=msg_desc,
                         sin=255,
                         min=4)
        dest_desc = 'An address code intended to map to a unique user'
        self.fields.add(UnsignedIntField(name='destination',
                                         size=32,
                                         data_type='uint_32',
                                         optional=True,
                                         description=dest_desc))
        self.fields.add(StringField(name='text', size=255, optional=True))
        self.fields.add(EnumField(name='helpCode',
                                  items=HELP_CODES,
                                  size=4,   # allow up to 16 help codes
                                  optional=True))
        ts_desc = json.dumps({
            'description': 'Seconds since 1970-01-01T00:00:00Z',
            'units': 'seconds'
        })
        self.fields.add(UnsignedIntField(name='timestamp',
                                         size=31,
                                         data_type='uint_32',
                                         optional=True,
                                         description=ts_desc))
        lat_desc = json.dumps({'units': 'degrees*60000'})
        self.fields.add(SignedIntField(name='latitude',
                                       size=24,
                                       data_type='int_32',
                                       optional=True,
                                       description=lat_desc))
        lng_desc = json.dumps({'units': 'degrees*60000'})
        self.fields.add(SignedIntField(name='longitude',
                                       size=25,
                                       data_type='int_32',
                                       optional=True,
                                       description=lng_desc))
        encoding = True if kwargs else False
        valid = False
        for kwarg in kwargs:
            if kwarg == 'text' and kwargs['text'] is not None:
                self.fields['text'].value = kwargs['text']
                valid = True
            elif kwarg == 'help_code' and kwargs['help_code'] is not None:
                help_code = kwargs['help_code']
                if help_code not in range(0, len(HELP_CODES)):
                    raise ValueError(f'Index {help_code} not in HELP_CODES')
                self.fields['helpCode'].value = help_code
                valid = True
            elif kwarg == 'location':
                location = kwargs['location']
                if isinstance(location, Location) and location.timestamp > 0:
                    lat = int(location.latitude * 60000)
                    lng = int(location.longitude * 60000)
                    self.fields['timestamp'].value = location.timestamp
                    self.fields['latitude'].value = lat
                    self.fields['longitude'].value = lng
                else:
                    logger.warning(f'Invalid location supplied, ignoring')
            elif kwarg == 'destination':
                dest = kwargs['destination']
                if not isinstance(dest, int) or dest not in range(0, 2**32):
                    raise ValueError(f'Invalid destination {dest}')
                self.fields['destination'].value = dest
            else:
                logger.warning(f'Ignoring unknown kwarg: {kwarg}')
        if encoding and not valid:
            raise ValueError(f'Missing at least one of text or help_code')


def test_optional_location():
    test_loc = {"latitude": 45.3365, "longitude": -75.90388, "resolution": 6, "altitude": 0.0, "speed": 0.0, "heading": 0.0, "timestamp": 1671797954, "satellites": 5, "fix_type": 1, "pdop": 3.0, "hdop": 3.0, "vdop": 3.0}
    MIN_TEST = 0
    for i in range(2):
        test_parms = {
            'destination': 1,
            'text': 'hello',
            'help_code': 1,
            'location': Location(**test_loc),
        }
        if i == MIN_TEST:   # only text
            test_parms.pop('location')
            test_parms.pop('help_code')
            test_parms.pop('destination')
        test_msg = TextMo(**test_parms)
        # assert test_msg.ota_size == 20
        payload_hex = test_msg.encode(data_format=DataFormat.HEX)['data']
        encoded = bytes.fromhex(f'{test_msg.sin:02x}{test_msg.min:02x}{payload_hex}')
        bin_encoded = ''.join([f'{b:08b}' for b in encoded])
        bin_payload = bin_encoded[16:]
        expected = {
            'destination': '1' + '0' * 31 + '1',
            'text': '1'+'000001010110100001100101011011000110110001101111',
            'helpCode': '1' + '0001',
            'timestamp': '1'+'1100011101001011001110011000010',
            'latitude': '1'+'001010011000000110111110',
            'longitude': '1'+'1101110101000001000001000',
        }
        if i == MIN_TEST:
            for f in ['destination', 'helpCode', 'timestamp', 'latitude', 'longitude']:
                expected[f] = '0'
        bin_fields = {}
        idx = 0
        for field in test_msg.fields:
            bin_fields[field.name] = bin_payload[idx:idx + field.bits]
            assert bin_fields[field.name] == expected[field.name]
            idx += field.bits
        comp_msg = TextMo()
        comp_msg.decode(encoded)
        assert comp_msg == test_msg
