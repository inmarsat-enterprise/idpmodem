"""AT Command protocol factory for pyserial-asyncio.

**WARNING**: This module is untested as a work in progress refactor of the
legacy atcommand_async module.

"""

import asyncio
import logging
from time import time

import serial_asyncio
from idpmodem.aterror import AtCrcError, AtTimeout
from idpmodem.crcxmodem import get_crc, validate_crc

_log = logging.getLogger(__name__)


class AtProtocol(asyncio.Protocol):
    
    TERMINATOR = '\r'
    ENCODING = 'utf-8'
    UNICODE_HANDLING = 'replace'
    DEFAULT_TIMEOUT = 5

    def __init__(self,
                 crc: bool = False,
                 event_callback: callable = None,
                 at_timeout: int = 5,
                 ):
        super().__init__()
        self.transport: asyncio.Transport = None
        self.crc = crc
        self.alive = True
        self.at_timeout = at_timeout
        self.pending_command = None
        self.command_time = None
        self.response_time = None
        self.response: 'list[str]' = []
        self.response_complete = False
        self.filter = None
        self._debug = False
        self.event_callback = event_callback

    def connection_made(self, transport) -> None:
        self.transport = transport
        _log.debug('Serial AT protocol connection opened')
    
    def connection_lost(self, exc) -> None:
        _log.warning('Serial AT procotol connection lost')
        self.transport.loop.stop()
        self.transport = None
        if isinstance(exc, Exception):
            raise exc

    def data_received(self, data: bytes) -> None:
        self.buffer.extend(data)
        if self.pending_command is not None:
            if data == b'\r':
                #: Echo case
                if self.buffer == self.pending_command.encode() + b'\r':
                    echo = self.buffer
                    #: reset buffer for response
                    self.buffer = bytearray(b'')
                    self.handle_packet(echo)
            elif data == b'\n':
                if (self.buffer != bytearray(b'\r\n')
                    and self.buffer != bytearray(b'\n')):
                    #: Framed/multiline response, error code or CRC
                    packet = self.buffer
                    self.buffer = bytearray(b'')
                    self.handle_packet(packet)
                elif self.buffer == bytearray(b'\n'):
                    #: (Unexpected) drop any empty lines
                    self.buffer = bytearray(b'')
        else:   # no pending command
            if data == b'\n':
                unsolicited = self.buffer
                self.buffer = bytearray(b'')
                self.handle_packet(unsolicited)

    def handle_packet(self, packet: bytearray):
        """Decodes packet(s) - inherited from LineReader."""
        self.handle_line(packet.decode(self.ENCODING, self.UNICODE_HANDLING))

    def handle_line(self, line: str):
        """Enqueues lines for parsing by command handler.

        Args:
            line: The unicode string received from the serial port.
        """
        if self.pending_command is not None:
            self.handle_response(line)
        else:
            if line != '\n':
                self.handle_event(line)

    def write_line(self, line: str):
        """Appends a terminator, encodes and writes text to the transport."""
        send: str = line + self.TERMINATOR
        self.transport.write(send.encode(self.ENCODING, self.UNICODE_HANDLING))
    
    def handle_event(self, unsolicited: str):
        """Calls a user-defined function with the unicode string.

        Args:
            unsolicited: A unicode string terminated by <lf>.

        """
        if unsolicited is not None:
            if self.event_callback is not None:
                self.event_callback(unsolicited)
            else: 
                unsolicited = unsolicited.replace('\r', '<cr>')
                unsolicited = unsolicited.replace('\n', '<lf>')
                _log.warning(f'Unhandled event: {unsolicited}')

    def handle_response(self, line: str):
        content = line.strip()
        if self.response_time is None:
            self.response_time = time()
        if content == self.pending_command:
            pass   # ignore echo
        elif content == 'OK':
            self.response.append(line)
            if '%CRC=0' in self.pending_command:
                self.crc = False
            if (not self.crc and '%CRC=1' not in self.pending_command):
                # No need to wait for CRC
                self.response_complete = True
        elif content.startswith('*'):
            if not self.crc:
                if not '%CRC=1' in self.pending_command:
                    _log.warning('Inferring CRC enabled')
                self.crc = True
            crc = content.replace('*', '')
            if not validate_crc(''.join(self.response), crc):
                raise AtCrcError(f'INVALID_CRC_RESPONSE')
            self.response_complete = True
        else:   #: including 'ERROR'
            self.response.append(line)
            # keep parsing in case CRC follows    

    def _clean_response(self,
                        lines: 'list[str]',
                        filter: 'list[str]' = [],
                        debug: bool = False,
                        ) -> 'list[str]':
        """Removes empty lines from response and returns a list.
        
        Args:
            lines: A list of reponse lines.
            filter: Optional list of strings/substrings to filter from response.
            debug: If True, logs the command latency
        
        Returns:
            List with filtered and stripped lines

        Raises:
            ValueError if filter is invalid.

        """
        if filter and not isinstance(filter, list):
            raise ValueError('filter must be a list of strings')
        if debug:
            latency = round(self.response_time - self.command_time, 3)
            _log.debug(f'Command {self.pending_command}'
                          f' latency: {latency} seconds')
        for l in range(len(lines)):
            lines[l] = lines[l].strip()
            if isinstance(filter, list) and len(filter) > 0:
                for s in filter:
                    if lines[l].startswith(s):
                        s += ':' if lines[l].startswith(f'{s}:') else ''
                        lines[l] = lines[l].replace(s, '').strip()
        return [x for x in lines if x != '']

    async def command(self,
                command: str,
                filter: 'list[str]' = [],
                timeout: int = 5,
                debug: bool = False,
                ) -> 'list[str]':
        """Send an AT command and wait for the response.

        Returns the response as a list.  If an error response code was
        received then 'ERROR' will be the only string in the list.

        .. todo: generalize for OK-only response, and provide error detail

        Args:
            command: The AT command
            timeout: Time to wait for response in seconds (default 5)
        
        Returns:
            A list of strings. The list will be ['ERROR'] in case of a problem.

        Raises:
            AtCrcError if CRC does not match.
            AtTimeout if the request timed out.

        """
        if self.pending_command is not None:
            raise 
        timeout = 1 if timeout < 1 else timeout
        command = get_crc(command) if self.crc else command
        self.pending_command = command
        self.response_complete = False
        self.response_time = None
        self.command_time = time()
        self.write_line(command)
        try:
            await self._timeout_check(timeout=timeout)
            return self._clean_response(self.response, filter, debug)
        except asyncio.TimeoutError:
            raise AtTimeout(f'TIMEOUT ({command})')
        finally:
            self._cleanup()

    async def _timeout_check(self):
        while not self.response_complete:
            await asyncio.sleep(1)

    def _cleanup(self):
        self.pending_command = None
        self.response = []
