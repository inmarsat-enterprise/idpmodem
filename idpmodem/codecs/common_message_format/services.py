from warnings import warn

from . import ET
from .base import BaseCodec, CodecList
from .messages import MessageCodec, Messages


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
        
    def xml(self) -> ET.Element:
        """Returns the Service XML definition for a Message Definition File."""
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
        return xservice


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
