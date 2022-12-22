from copy import deepcopy

from .. import ET
from .base_field import FieldCodec, Fields
from .helpers import decode_field_length, encode_field_length


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
            assert isinstance(field, FieldCodec)
            bits += field.bits
        return bits + (1 if self.optional else 0)
    
    def _valid_element(self, element: Fields) -> bool:
        for i, field in enumerate(self.fields):
            assert isinstance(field, FieldCodec)
            e_field = element[i]
            assert isinstance(e_field, FieldCodec)
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

    def append(self, element: Fields):
        """Adds the array element to the list of elements."""
        if not isinstance(element, Fields):
            raise ValueError('Invalid element definition must be Fields')
        if not self._valid_element(element):
            raise ValueError('Invalid element definition'
                             f' - requires {self.fields}')
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
        self.append(Fields(new_fields))
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
            binstr = encode_field_length(len(self.elements)) + binstr
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
        """Returns the Array XML definition for a Message Definition File."""
        # Size must come after Fields for Inmarsat V1 parser
        xmlfield = self._base_xml()
        if self.fixed:
            default = ET.SubElement(xmlfield, 'Fixed')
            default.text = 'true'
        fields = ET.SubElement(xmlfield, 'Fields')
        for field in self.fields:
            assert isinstance(field, FieldCodec)
            fields.append(field.xml())
        size = ET.SubElement(xmlfield, 'Size')
        size.text = str(self.size)
        return xmlfield
