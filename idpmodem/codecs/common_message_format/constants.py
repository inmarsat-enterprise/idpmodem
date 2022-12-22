XML_NAMESPACE = {
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    'xsd': 'http://www.w3.org/2001/XMLSchema'
}

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
    'array': 'ArrayField',
}

SIN_RANGE = (16, 255)
