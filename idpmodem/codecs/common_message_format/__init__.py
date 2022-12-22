import xml.etree.ElementTree as ET

from .base import BaseCodec, CodecList
from .constants import *
from .fields import (ArrayField, BooleanField, DataField, EnumField,
                     SignedIntField, StringField, UnsignedIntField)
from .fields.base_field import FieldCodec, Fields
from .fields.helpers import optimal_bits
from .message_definitions import MessageDefinitions
from .messages import MessageCodec, Messages
from .services import ServiceCodec, Services

for ns in XML_NAMESPACE:
    ET.register_namespace(ns, XML_NAMESPACE[ns])
