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

    def _attribute_equivalence(self,
                               other: object,
                               exclude: "list[str]" = None) -> bool:
        """Indicates attribute equivalence, with optional exceptions."""
        if not isinstance(other, self.__class__):
            return NotImplemented
        for attr, val in self.__dict__.items():
            if exclude is not None and attr in exclude:
                continue
            if not hasattr(other, attr) or val != other.__dict__[attr]:
                return False
        return True
    
    def __eq__(self, other: object) -> bool:
        return self._attribute_equivalence(other)


class CodecList(list):
    """Base class for a specific object type list.
    
    Used for Fields, Messages, Services.

    Attributes:
        codec_cls: The object type the list is comprised of.

    """
    def __init__(self, codec_cls: BaseCodec):
        super().__init__()
        self.list_type = codec_cls

    def add(self, codec: BaseCodec) -> bool:
        """Add an object to the end of the list.

        Args:
            obj (object): A valid object according to the list_type
        
        Raises:
            ValueError if there is a duplicate or invalid name,
                invalid value_range or unsupported data_type
        """
        if not isinstance(codec, self.list_type):
            raise ValueError(f'Invalid {self.list_type} definition')
        for o in self:
            if o.name == codec.name:
                raise ValueError(f'Duplicate {self.list_type}'
                                 f' name {codec.name} found')
        self.append(codec)
        return True

    def __getitem__(self, n: 'str|int') -> BaseCodec:
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
