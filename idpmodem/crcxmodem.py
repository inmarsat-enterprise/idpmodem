#!/usr/bin/env python
"""Calculates CRC-16-CCITT checksum for xmodem.

Intended for use with SkyWave/ORBCOMM IDP modem.

Thanks to: https://stackoverflow.com/questions/25239423/crc-ccitt-16-bit-python-manual-calculation.

"""
import logging
import os

from idpmodem.helpers import printable_crlf

VERBOSE_DEBUG = str(os.getenv('VERBOSE_DEBUG', False)).lower() == 'true'

_log = logging.getLogger(__name__)
__version__ = "1.1.0"

POLYNOMIAL = 0x1021
PRESET = 0


def _initial(c: int) -> int:
    """Sets up the polynomial lookup table."""
    _crc = 0
    c = c << 8
    for _ in range(8):
        if (_crc ^ c) & 0x8000:
            _crc = (_crc << 1) ^ POLYNOMIAL
        else:
            _crc = _crc << 1
        c = c << 1
    return _crc


_tab = [_initial(i) for i in range(256)]


def _update_crc(_crc: int, c: int) -> int:
    """Updates the CRC during iteration."""
    cc = 0xff & c
    tmp = (_crc >> 8) ^ cc
    _crc = (_crc << 8) ^ _tab[tmp & 0xff]
    _crc = _crc & 0xffff
    return _crc


def crc(string: str, initial: int = 0xffff) -> int:
    """Returns the CRC value.

    Args:
        string: the text to have CRC calculated on
        initial: the start value of CRC (0xFFFF for IDP modem)
    
    Returns:
        The CRC-16-CCITT value
    """
    _crc = initial
    for c in string:
        _crc = _update_crc(_crc, ord(c))
    return _crc


''' Unused
def crc_bytes(*i) -> int:
    """Returns the CRC value of a byte stream.

    Args:
        i: byte stream
    
    Returns:
        crc value
    """
    _crc = PRESET
    for b in i:
        _crc = _update_crc(_crc, b)
    return _crc
'''


def get_crc(command: str) -> str:
    """Returns the command with CRC in format `command*<crc>`.
    
    Deprecate - replace with `apply_crc`.
    Calculates and applies a CCITT-16 checksum for an AT command.

    Args:
        command: The AT command or response to calculate CRC on
    
    Returns:
        The command with CRC appended after *

    """
    return f'{command}*{crc(command):04X}'


def apply_crc(command: str) -> str:
    """Returns the command with CRC in format `command*<crc>`.
    
    Calculates and applies a CCITT-16 checksum for an AT command.

    Args:
        command: The AT command or response to calculate CRC on
    
    Returns:
        The command with CRC appended after *

    """
    return f'{command}*{crc(command):04X}'


def validate_crc(response: str, candidate: str) -> bool:
    """Calculates and validates the response CRC against expected.
    
    Args:
        response: The response received without CRC (before *)
        candidate: The CRC received (after *)
    
    Returns:
        True if the candidate matches the expected CRC of the response.

    """
    expected = f'{crc(response):04X}'
    if expected == candidate.replace('*', ''):
        return True
    if VERBOSE_DEBUG:
        _log.debug(f'{printable_crlf(response)}'
                   f' expected *{expected} got *{candidate}')
    return False


def main():
    try:
        from builtins import input
    except ImportError:
        pass
    s = input('Enter string: ')
    print(f'0x{crc(s, 0xffff):04X}')


if __name__ == "__main__":
    main()
