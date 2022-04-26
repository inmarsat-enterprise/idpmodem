# -*- coding: utf-8 -*-
"""AT command protocol (threaded) for Inmarsat IDP satellite messaging modems.

This module provides a threaded serial interface that sends and receives 
AT commands, decoding/abstracting typically used operations.
Based on the PySerial threaded protocol factory, using a byte reader.

"""

import logging
import queue
import threading
from time import sleep, time

from serial import Serial, SerialException
from serial.threaded import LineReader, ReaderThread, Protocol

from idpmodem.aterror import AtCrcError, AtTimeout
from idpmodem.crcxmodem import apply_crc, validate_crc


_log = logging.getLogger(__name__)


class AtProtocol(LineReader):
    """Threaded protocol factory for the IDP Modem.
    
    Maintains queues for requests, responses and unsolicited reports using
    task objects with callbacks.

    Accepts only one AT command at a time.  Handles command echo 
    terminated with <cr>, verbose response framed with <cr><lf>, 
    unsolicited data terminated with <lf>, and CRC error checking.

    Attributes:
        alive (bool): True while the factory is running.
        crc (bool): Indicates if CRC error checking is enabled.
        pending_command (str): The AT command being processed.
        responses (Queue): Queued responses to be processed as a line.
        unsolicited (Queue): Unexpected data received if no pending command.
        event_callback (Callable): optional callback function for 
        unexpected data
    """

    TERMINATOR = '\r'
    ENCODING = 'utf-8'
    UNICODE_HANDLING = 'replace'
    DEFAULT_TIMEOUT = 5

    def __init__(self,
                 event_callback: callable = None,
                 at_timeout: int = 5):
        """Initialize with CRC and optional callback

        Args:
            crc: Use CRC error checking (for long serial line).
            event_callback: Handler for non-command data.

        """
        super().__init__()
        # self.buffer = bytearray()   #: inherited from LineReader/Packetizer
        # self.transport = None   #: inherited from LineReader/Packetizer
        self.crc = False   #: This will be inferred from communications
        self.alive = True
        self.at_timeout = at_timeout
        self.pending_command = None
        self.command_time = None
        self.response_time = None
        self.responses = queue.Queue()
        self.events = queue.Queue()
        self._event_thread = threading.Thread(target=self._run_event,
                                              name='at_unsolicited',
                                              daemon=True)
        self._event_thread.start()
        self._lock = threading.Lock()
        self.event_callback = event_callback

    # def connection_made(self, transport):
    #     """Store transport - inherited from LineReader/Packetizer."""
    #     self.transport = transport

    # def connection_lost(self, exc):
    #     """Forget transport - inherited from LineReader/Packetizer."""
    #     self.transport = None
    #     if isinstance(exc, Exception):
    #         raise exc

    def data_received(self, data: bytearray):
        """Buffer received data and create packets for handlers.

        handle_packet() is inherited from LineReader.

        Args:
            data: a data byte received from the serial device

        """
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

    # def handle_packet(self, packet: bytearray):
    #     """Decodes packet(s) - inherited from LineReader."""
    #     self.handle_line(packet.decode(self.ENCODING, self.UNICODE_HANDLING))

    def handle_line(self, line: str):
        """Enqueues lines for parsing by command handler.

        Args:
            line: The unicode string received from the serial port.
        """
        if self.pending_command is not None:
            self.responses.put(line)
        else:
            if line != '\n':
                self.events.put(line)

    def write_line(self, text):
        """Appends a terminator, encodes and writes text to the transport."""
        send = text + self.TERMINATOR
        self.transport.write(send.encode(self.ENCODING, self.UNICODE_HANDLING))
    
    def stop(self):
        """Stop the event processing thread and abort pending commands."""
        self.alive = False
        self.events.put(None)
        self.responses.put('<exit>')

    def _run_event(self):
        """Process events (unsolicited messages) in a separate thread.
        
        Ensures the command response thread is not blocked.

        Raises:
            AtUnsolicited: If an unexpected handling error occurs.
        
        """
        while self.alive:
            try:
                self.handle_event(self.events.get())
            except:
                _log.exception(f'Unexpected _run_event error')

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

    def command(self,
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
        with self._lock:  # ensure that just one thread is sending commands at once
            try:
                oldbuffer: str = self.responses.get(timeout=0.05)
                _log.warning(f'Cleared old buffer: {oldbuffer}')
            except queue.Empty:
                pass
            timeout = 1 if timeout < 1 else timeout
            command = apply_crc(command) if self.crc else command
            self.pending_command = command
            self.command_time = time()
            self.response_time = None
            self.write_line(command)
            lines = []
            while self.pending_command is not None:
                try:
                    line: str = self.responses.get(timeout=timeout)
                    content = line.strip()
                    if self.response_time is None:
                        self.response_time = time()
                    if content == command:
                        pass   # ignore echo
                    elif content in ['OK', 'ERROR']:
                        lines.append(line)
                        if self.crc and '%CRC=0' in self.pending_command:
                            _log.debug('CRC disabled by command')
                            self.crc = False
                        if (not self.crc and
                            '%CRC=1' not in self.pending_command):
                            # No need to wait for CRC
                            return self._clean_response(lines, filter, debug)
                    elif content.startswith('*'):
                        if not self.crc:
                            if not '%CRC=1' in self.pending_command:
                                _log.debug('Found CRC enabled')
                            self.crc = True
                        crc = content.replace('*', '')
                        if not validate_crc(''.join(lines), crc):
                            raise AtCrcError(f'INVALID_CRC_RESPONSE')
                        return self._clean_response(lines, filter, debug)
                    else:   #: including 'ERROR'
                        lines.append(line)
                        # keep parsing in case CRC follows
                except queue.Empty:
                    if not self.response_time:
                        raise AtTimeout(f'TIMEOUT ({timeout}s)')
                    return self._clean_response(lines, filter, debug)


class ByteReaderThread(ReaderThread):
    """Modifies the ReaderThread class to process bytes individually.
    
    This is required due to complexities of optional checksum use 
    for long serial lines.

    """
    def __init__(self,
                 serial_instance: Serial,
                 protocol_factory: Protocol,
                 **kwargs):
        super().__init__(serial_instance, protocol_factory)
        self.name = None
        self.kwargs = kwargs

    def run(self):
        """Reader loop"""
        self.name = f'bytereader@{self.serial.name}'
        if not hasattr(self.serial, 'cancel_read'):
            self.serial.timeout = 1
        self.protocol = self.protocol_factory(**self.kwargs)
        try:
            self.protocol.connection_made(self)
        except Exception as err:
            self.alive = False
            self.protocol.connection_lost(err)
            self._connection_made.set()
            return
        error = None
        self._connection_made.set()
        data = bytearray()
        while self.alive and self.serial.is_open:
            try:
                # read all that is there or wait for one byte (blocking)
                if self.serial.in_waiting > 0:
                    data = self.serial.read()
                    self.protocol.data_received(data)
                sleep(0.001)
            except SerialException as err:
                # probably some I/O problem such as disconnected USB serial
                # adapters -> exit
                error = err
                break
            except Exception as err:
                error = err
                break
        self.alive = False
        self.protocol.connection_lost(error)
        self.protocol = None
