from .. import DATA_TYPES, ET, BaseCodec, CodecList


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

    # def __eq__(self, other: object) -> bool:
    #     """Must be subclassed.
        
    #     Args:
    #         other: The other thing being compared to this.

    #     """
    #     raise NotImplementedError('Subclass must define equivalence')

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
