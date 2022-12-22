from copy import deepcopy

from . import ET, XML_NAMESPACE
from .services import ServiceCodec, Services


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
    
    def xml(self) -> ET.Element:
        """Gets the XML structure of the complete message definitions."""
        xmsgdef = ET.Element('MessageDefinition',
                             attrib={'xmlns:xsd': XML_NAMESPACE['xsd']})
        services = ET.SubElement(xmsgdef, 'Services')
        for service in self.services:
            assert isinstance(service, ServiceCodec)
            services.append(service.xml())
        return xmsgdef
    
    def mdf_export(self,
                   filename: str,
                   pretty: bool = False,
                   indent: int = 0,
                   include_service_description: bool = False,
                   ) -> None:
        """Creates an XML file at the target location.
        
        Args:
            filename: The full path/filename to save to. `.idpmsg` is
                recommended as a file extension.
            pretty: If True sets indent = 2 (legacy compatibility)
            indent: If nonzero will indent each layer of the XML by n spaces.
            include_service_description: By default removes Description from
                Service for Inmarsat IDP Admin API V1 compatibility.

        """
        if not include_service_description:
            new_copy = deepcopy(self)
            for service in new_copy.services:
                assert isinstance(service, ServiceCodec)
                if service.description is not None:
                    service.description = None
            tree = ET.ElementTree(new_copy.xml())
        else:
            tree = ET.ElementTree(self.xml())
        if pretty:
            indent = 2
        if indent:
            root = tree.getroot()
            _indent(root, spaces=indent)
            xmlstr = ET.tostring(root).decode()
            with open(filename, 'w') as f:
                f.write(xmlstr)
        else:
            with open(filename, 'wb') as f:
                tree.write(f, encoding='utf-8', xml_declaration=True)


def _indent(elem: ET.Element, level: int = 0, spaces: int = 2) -> ET.Element:
    i = '\n' + level * (' ' * spaces)
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + ' ' * spaces
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        sub_index = 0
        for subelem in elem:
            sub_index += 1
            _indent(subelem, level + 1)
            if sub_index == len(elem):
                subelem.tail = i
        # if not elem.tail or not elem.tail.strip():
        #     elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i
    if level == 0:
        elem.tail = None
