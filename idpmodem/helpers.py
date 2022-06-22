"""Helpers for working with serial ports and encoding conversions.

"""
import binascii
from string import printable

import serial.tools.list_ports as list_ports


def validate_serial_port(target: str, verbose: bool = False) -> 'bool|tuple':
    """Validates a given serial port as available on the host.

    When working with different OS and platforms, using a serial port to connect
    to a modem can be simplified by *validate_serial_port*.

    If target port is not found, a list of available ports is returned.
    Labels known FTDI and Prolific serial/USB drivers.

    Args:
        target: Target port name e.g. ``/dev/ttyUSB0``
    
    Returns:
        True or False if detail is False
        (valid: bool, description: str) if detail is True
    """
    found = False
    detail = ''
    ser_ports = [tuple(port) for port in list(list_ports.comports())]
    for port in ser_ports:
        if target == port[0]:
            found = True
            usb_id = str(port[2])
            if 'USB VID:PID=0403:6001' in usb_id:
                driver = 'Serial FTDI FT232 (RS485/RS422/RS232)'
            elif 'USB VID:PID=067B:2303' in usb_id:
                driver = 'Serial Prolific PL2303 (RS232)'
            else:
                driver = 'Serial vendor/device {}'.format(usb_id)
            detail = '{} on {}'.format(driver, port[0])
    if not found and len(ser_ports) > 0:
        for port in ser_ports:
            if len(detail) > 0:
                detail += ','
            detail += " {}".format(port[0])
        detail = 'Available ports:' + detail
    return (found, detail) if verbose else found


def is_hex_string(s: str) -> bool:
    """Returns True if the string consists exclusively of hexadecimal chars."""
    hex_chars = '0123456789abcdefABCDEF'
    return all(c in hex_chars for c in s)


def bytearray_to_str(arr: bytearray) -> str:
    """Converts a bytearray to a readable text string."""
    s = ''
    for b in bytearray(arr):
        if chr(b) in printable:
            s += chr(b)
        else:
            s += '{0:#04x}'.format(b).replace('0x', '\\')
    return s


def bytearray_to_hex_str(arr: bytearray) -> str:
    """Converts a bytearray to a hex string."""
    return binascii.hexlify(bytearray(arr)).decode()


def bytearray_to_b64_str(arr: bytearray) -> str:
    """Converts a bytearray to a base64 string."""
    return binascii.b2a_base64(bytearray(arr)).strip().decode()


def printable_crlf(line: str) -> str:
    """Returns a line with CR and LF replaced."""
    return line.replace('\r', '\\r').replace('\n', '\\n')
