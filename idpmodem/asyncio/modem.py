"""IDP Modem abstraction for pyserial-asyncio.

**WARNING**: This module is untested as a work in progress refactor of the
legacy atcommand_async module.

"""

import asyncio
import logging
import queue
from base64 import b64decode, b64encode
from datetime import datetime, timezone
from time import time

import serial_asyncio
from idpmodem.aterror import AtException, AtGnssTimeout
from idpmodem.constants import (AT_ERROR_CODES, EVENT_TRACES, GEOBEAMS,
                                POWER_MODES, WAKEUP_PERIODS, BeamSearchState,
                                DataFormat, EventNotification, MessagePriority,
                                MessageState, SatlliteControlState, TransmitterStatus)
from idpmodem.location import Location, location_from_nmea
from idpmodem.s_registers import SRegisters
from idpmodem.asyncio.atcommand import AtProtocol

GNSS_STALE_SECS = 1
GNSS_WAIT_SECS = 35
SAT_STATUS_HOLDOFF = 5

_log = logging.getLogger(__name__)


class ModemBusy(Exception):
    """Indicates the modem is busy processing a prior command."""


class AtConfiguration:
    def __init__(self) -> None:
        self.crc: bool = False
        self.echo: bool = True
        self.quiet: bool = False
        self.verbose: bool = True


class IdpModem:
    """A protocol factory abstracting AT commands for an IDP modem."""
    
    SERIAL_KWARGS = ['baudrate', 'timeout', 'write_timeout']
    BAUD_RATES = [1200, 2400, 4800, 9600, 19200]
    PROTOCOL_KWARGS = ['event_callback', 'at_timeout']
    OTHER_KWARGS = ['error_detail', 'debug', 'stale_secs', 'wait_secs']
    
    def __init__(self, serial_port: str, **kwargs):
        self.serial_kwargs = {
            'port': serial_port,
            'baudrate': int(kwargs.pop('baudrate', 9600)),
        }
        self.protocol_kwargs = {}
        self.error_detail = bool(kwargs.pop('error_detail', True))
        self.debug = bool(kwargs.pop('debug', False))
        for kwarg in kwargs:
            if kwarg in self.SERIAL_KWARGS:
                self.serial_kwargs[kwarg] = kwargs[kwarg]
            elif kwarg in self.PROTOCOL_KWARGS:
                self.protocol_kwargs[kwarg] = kwargs[kwarg]
        self.loop = asyncio.get_event_loop()
        self.coro = serial_asyncio.create_serial_connection(
            self.loop,
            protocol_factory=AtProtocol,
            **self.serial_kwargs
        )
        self.serial_port = None
        self.transport = None
        self.protocol = None
        self.commands = queue.Queue(1)
        self._at_config = AtConfiguration()
        self._mobile_id: str = None
        self._versions: dict = None
        self._power_mode: int = None
        self._wakeup_period: int = None
        self._ctrl_state: int = None
        self._snr: float = None
        self._geo_beam_id: int = None
        self._beamsearch_state: int = None
        self._loc_query: dict = {
            'stale_secs': int(kwargs.pop('stale_secs', GNSS_STALE_SECS)),
            'wait_secs': int(kwargs.pop('wait_secs', GNSS_WAIT_SECS)),
        }
        self._holdoffs: dict = {}   # used to ignore frequent repeat commands
        self._statistics: dict = {}
        self.s_registers = SRegisters()
        # self.tx_queue = queue.Queue()
        # self.tx_complete_callback: callable = None
        # self.rx_queue = queue.Queue()
        # self.rx_received_callback: callable = None
    
    def connect(self):
        self.transport, self.protocol = self.loop.run_until_complete(self.coro)
        self.loop.run_forever()
        _log.debug(f'Transport: {self.transport}')
        # self.serial_port = Serial(**self.serial_kwargs)

    def disconnect(self):
        self.loop.close()
        self.transport = None
        self.protocol = None
    
    @property
    def connected(self) -> bool:
        return self.transport is not None and self.protocol is not None

    @property
    def baudrate(self) -> 'int|None':
        return self.transport.baudrate if self.transport else None
    
    @baudrate.setter
    def baudrate(self, value: int):
        if not self.connected:
            raise ConnectionError('Modem is not connected')
        if value not in self.BAUD_RATES:
            raise ValueError(f'Baud rate must be one of {self.BAUD_RATES}')
        response = self.atcommand(f'AT+IPR={value}')
        if response and response[0] != 'ERROR':
            self.serial_port.baudrate = value

    @property
    def crc(self) -> 'bool|None':
        return self.protocol.crc if self.protocol is not None else None

    def atcommand(self,
                  command: str,
                  filter: 'list[str]' = [],
                  timeout: int = 5,
                  await_previous: bool = True,
                  ) -> 'list[str]':
        """Sends an AT command to the modem and returns the response.
        
        Args:
            command: The AT command
            filter: (optional) list of sub/strings to remove from response.
            timeout: Number of seconds to wait for a reply
                (not including messages queued by other threads)
            await_previous: If True, this will block if a prior command was
                submitted by another thread
        
        Returns:
            list of filtered and stripped response(s) to the command(s)
        
        Raises:
            ModemBusy if await_previous is False and a prior command is queued.
            AtException if an error occurred that is unrecognized.

        """
        if not self.connected:
            raise ConnectionError('No connection to IDP modem')
        while self.commands.full():
            if not await_previous:
                raise ModemBusy
            pass
        self.commands.put(command)
        # TODO: allow for async(?)
        res: list = self.protocol.command(command, filter, timeout, self.debug)
        if self.error_detail and res and res[0] == 'ERROR':
            _log.error(f'Error received for command {command}')
            err_res = self.protocol.command('ATS80?')
            if not err_res or err_res[0] == 'ERROR':
                raise AtException('Unhandled error getting last error code')
            last_err_code = err_res[0]
            detail = 'UNDEFINED'
            if int(last_err_code) in AT_ERROR_CODES:
                detail = AT_ERROR_CODES[int(last_err_code)]
            res.append(f'{detail} ({last_err_code})')
        self.commands.get()
        self.commands.task_done()
        return res
    
    def _handle_at_exception(self, response: 'list[str]') -> None:
        err = response[1] if self.error_detail else response[0]
        raise AtException(err)

    def config_init(self, crc: bool = False) -> bool:
        """Initializes modem communications with Echo, Verbose. CRC optional."""
        def attempt(command: str) -> bool:
            response = self.atcommand(command)
            return response[0] == 'OK'
        # try at most twice
        command = f'ATZ;E1;V1;Q0;%CRC={1 if crc else 0}'
        success = attempt(command)
        if not success:
            success = attempt(command)
        if success:
            self.protocol.crc = crc
            self._at_config.crc = crc
        return success

    def config_restore_nvm(self) -> bool:
        """Sends ATZ to restore config from non-volatile memory."""
        response = self.atcommand('ATZ')
        if response[0] == 'ERROR':
            return False
        return True

    def config_restore_factory(self) -> bool:
        """Sends AT&F to restore factory default and returns True on success."""
        response = self.atcommand('AT&F')
        if response[0] == 'ERROR':
            return False
        return True
    
    def config_report(self) -> 'tuple[dict, dict]':
        """Sends the AT&V command to retrieve S-register settings.
        
        Returns:
            A tuple with two dictionaries (empty if failed) with:
            at_config with booleans crc, echo, quiet and verbose
            reg_config with S-register tags and integer values
        
        Raises:
            AtException if an error was returned.

        """
        response = self.atcommand('AT&V')
        if response[0] == 'ERROR':
            self._handle_at_exception(response)
        at_config = response[1]
        s_regs = response[2]
        echo, quiet, verbose, crc = at_config.split(' ')
        self._at_config.crc = bool(int(crc[4]))
        self._at_config.echo = bool(int(echo[1]))
        self._at_config.quiet = bool(int(quiet[1]))
        self._at_config.verbose = bool(int(verbose[1]))
        reg_config = {}
        for reg in s_regs.split(' '):
            name, value = reg.split(':')
            reg_config[name] = int(value)
        return (at_config, reg_config)

    def config_volatile_report(self) -> 'dict|None':
        """Returns key S-register settings.
        
        GNSS Mode (S39), GNSS fix timeout (S41), GNSS Continuous (S55),
        GNSS Jamming Status (S56), GNSS Jamming Indicator (S57), 
        Low power Wakeup Period (S51)

        Returns:
            Dictionary of S-register values, or None if failed
            
        """
        register_list = [
            'S39',   #: GNSS Mode
            'S41',   #: GNSS Fix Timeout
            'S51',   #: Wakeup Interval
            'S55',   #: GNSS Continuous
            'S56',   #: GNSS Jamming Status
            'S57',   #: GNSS Jamming Indicator
        ]
        command = 'AT'
        for reg in register_list:
            command += f'{reg if command == "AT" else " " + reg}?'
        response = self.atcommand(command)
        if response[0] == 'ERROR':
            return None
        #: else
        response.remove('OK')
        volatile_regs = {}
        for r in range(len(response)):
            volatile_regs[register_list[r]] = int(response[r])
        return volatile_regs

    def config_nvm_save(self) -> bool:
        """Sends the AT&W command and returns True if successful."""
        response = self.atcommand('AT&W')
        return response[0] == 'OK'

    def crc_enable(self, enable: bool = True) -> bool:
        """Sends the AT%CRC command and returns success flag.
        
        Args:
            enable: turn on CRC if True else turn off

        Returns:
            True if the operation succeeded else False

        """
        command = f'AT%CRC={1 if enable else 0}'
        response = self.atcommand(command)
        if response[0] == 'ERROR':
            return False
        self.protocol.crc = enable
        self._at_config.crc = enable
        return True

    @property
    def mobile_id(self) -> 'str|None':
        """Returns the unique Mobile ID (Inmarsat serial number)."""
        if self._mobile_id is None:
            response = self.atcommand('AT+GSN', filter=['+GSN:'])
            if response[0] != 'ERROR':
                self._mobile_id = response[0]
        return self._mobile_id

    @property
    def versions(self) -> 'dict|None':
        """Returns the hardware, firmware and AT versions."""
        if not self._versions:
            response = self.atcommand('AT+GMR', filter=['+GMR:'])
            if response[0] != 'ERROR':
                fw_ver, hw_ver, at_ver = response[0].split(',')
                self._versions = {
                    'hardware': hw_ver,
                    'firmware': fw_ver,
                    'at': at_ver,
                }
        return self._versions

    @property
    def power_mode(self) -> 'str|None':
        if self._power_mode is None:
            response = self.atcommand('ATS50?')
            if response[0] != 'ERROR':
                self._power_mode = int(response[0])
        if self._power_mode in POWER_MODES:
            return POWER_MODES[self._power_mode]
    
    @power_mode.setter
    def power_mode(self, value: 'str|int'):
        if isinstance(value, str):
            if value not in POWER_MODES.values():
                raise ValueError(f'Invalid power mode {value}')
            for k, v in POWER_MODES.items():
                if v == value:
                    value = k
                    break
        if value not in POWER_MODES:
            raise ValueError(f'Invalid power mode {value}')
        response = self.atcommand(f'ATS50={value}')
        if response[0] == 'OK':
            self._power_mode = value
    
    @property
    def wakeup_period(self) -> 'str|None':
        if self._wakeup_period is None:
            response = self.atcommand('ATS51?')
            if response[0] != 'ERROR':
                self._wakeup_period = int(response[0])
        if self._wakeup_period in WAKEUP_PERIODS:
            return WAKEUP_PERIODS[self._wakeup_period]

    @wakeup_period.setter
    def wakeup_period(self, value: 'str|int'):
        if isinstance(value, str):
            if value not in WAKEUP_PERIODS.values():
                raise ValueError(f'Invalid wakeup period {value}')
            for k, v in WAKEUP_PERIODS.items():
                if v == value:
                    value = k
                    break
        if value not in WAKEUP_PERIODS:
            raise ValueError(f'Invalid wakeup period {value}')
        response = self.atcommand(f'ATS51={value}')
        if response[0] == 'OK':
            self._wakeup_period = value
    
    @property
    def gnss_refresh_interval(self) -> int:
        response = self.atcommand(f'ATS55?')
        if response[0] != 'ERROR':
            return int(response[0])

    @gnss_refresh_interval.setter
    def gnss_refresh_interval(self, value: int):
        self.gnss_continuous_set(value)

    def gnss_continuous_set(self,
                            interval: int = 0,
                            doppler: bool = True,
                            ) -> bool:
        """Sets the GNSS continous mode (0 = on-demand).
        
        Args:
            interval: Seconds between GNSS refresh.
            doppler: Often required for moving assets.
        
        Returns:
            True if successful setting.
        """
        if interval < 0 or interval > 30:
            raise ValueError('GNSS continuous interval must be in range 0..30')
        response = self.atcommand(f'AT%TRK={interval}{",1" if doppler else ""}')
        if response[0] == 'ERROR':
            return False
        return True

    def gnss_nmea_get(self,
                      stale_secs: int = GNSS_STALE_SECS,
                      wait_secs: int = GNSS_WAIT_SECS,
                      nmea: 'list[str]' = ['RMC', 'GSA', 'GGA', 'GSV'],
                      ) -> list:
        """Returns a list of NMEA-formatted sentences from GNSS.

        Args:
            stale_secs: Maximum age of fix in seconds (1..600)
            wait_secs: Maximum time to wait for fix (1..600)

        Returns:
            List of NMEA sentences

        Raises:
            ValueError if parameter out of range
            AtGnssTimeout if the fix timed out
            AtException if any other error code was returned

        """
        NMEA_SUPPORTED = ['RMC', 'GGA', 'GSA', 'GSV']
        BUFFER_SECONDS = 5
        if (stale_secs not in range(1, 600+1) or
            wait_secs not in range(1, 600+1)):
            raise ValueError('stale_secs and wait_secs must be 1..600')
        sentences = ''
        for sentence in nmea:
            sentence = sentence.upper()
            if sentence not in NMEA_SUPPORTED:
                raise ValueError(f'Unsupported NMEA sentence: {sentence}')
            if len(sentences) > 0:
                sentences += ','
            sentences += f'"{sentence}"'
        timeout = wait_secs + BUFFER_SECONDS
        request_time = time()
        response = self.atcommand(f'AT%GPS={stale_secs}'
                                        f',{wait_secs},{sentences}',
                                        timeout=timeout,
                                        filter=['%GPS:'])
        if response[0] == 'ERROR':
            if self.error_detail:
                if 'TIMEOUT' in response[1]:
                    raise AtGnssTimeout(response[1])
            self._handle_at_exception(response)
        response.remove('OK')
        time_to_fix = round(time() - request_time, 3)
        if 'gnss_ttf' not in self._statistics:
            self._statistics['gnss_ttf'] = time_to_fix
        else:
            old_ttf = self._statistics['gnss_ttf']
            avg_ttf = round((time_to_fix + old_ttf) / 2, 3)
            self._statistics['gnss_ttf'] = avg_ttf
        return response

    @property
    def location(self) -> 'Location|None':
        try:
            nmea_sentences = self.gnss_nmea_get(self._loc_query['stale_secs'],
                                                self._loc_query['wait_secs'])
            return location_from_nmea(nmea_sentences)
        except:
            return None

    def message_mo_send(self,
                        data: 'bytes|bytearray|str',
                        data_format: int = DataFormat.BASE64,
                        name: str = None,
                        priority: int = MessagePriority.LOW,
                        sin: int = None,
                        min: int = None,
                        ) -> str:
        """Submits a mobile-originated message to send.

        When submitting raw bytes, the first byte will be used as SIN. The
        first byte must not be in the reserved range (0..15).
        When submitting a string, the `sin` field is expected to be set and
        the data field will be appended to the `sin` byte and optionally the
        `min` byte if specified.
        
        Args:
            data: The data raw bytes or UTF-8 Text, Hexadecimal or Base64 string
            data_format: 1=text, 2=hexadecimal, 3=base64 (default)
            name: Optional unique name up to 8 characters long. If none is
                specified, use the 8 least-significant digits of unix timestamp.
            priority: 1=high, 4=low (default)
            sin: Optional first byte of payload used for codec, required if data
                is string type.
            min: Optional second byte of payload used for codec

        Returns:
            Name of the message if successful, or the error string.
        
        Raises:
            AtException if an error was returned by the modem.

        """
        name = str(int(time()))[-8:] if not name else name[0:8]
        if isinstance(data, bytes) or isinstance(data, bytearray):
            sin = data[0]
            data = b64encode(data[1:]).decode('utf-8')
            data_format = DataFormat.BASE64
        elif not isinstance(data, str):
            raise ValueError('Invalid data must be bytes, bytearray or string')
        elif not isinstance(sin, int) or sin not in range(16, 256):
            raise ValueError('Invalid SIN must be 16..255')
        if isinstance(min, int) and min not in range(0, 256):
            raise ValueError('Invalid MIN must be 0..255')
        min = f'.{min}' if min is not None else ''
        data = f'"{data}"' if data_format == DataFormat.TEXT else data
        command = f'AT%MGRT="{name}",{priority},{sin}{min},{data_format},{data}'
        response = self.atcommand(command)
        if response[0] == 'ERROR':
            self._handle_at_exception(response)
        return name

    def message_mo_state(self, name: str = None) -> 'list[dict]':
        """Returns the message state(s) requested.
        
        If no name filter is passed in, all available messages states
        are returned.  Returns False is the request failed.

        Args:
            name: The unique message name in the modem queue. If none is
                provided, all available message states in transmit queue will be
                returned.

        Returns:
            List of metadata for each message in transmit queue including:
            - `name` (str) The ID in the modem transmit queue
            - `state` (int) The state of the message
            - `state_name` (str) The `MessageState.name`
            - `size` (int) in bytes
            - `sent` (int) in bytes for large message progress

        """
        states = []
        name = f'="{name}"' if name is not None else ''
        response = self.atcommand(f'AT%MGRS{name}', filter=['%MGRS:'])
        # %MGRS: "<name>",<msg_no>,<priority>,<sin>,<state>,<size>,<sent_bytes>
        if response[0] != 'ERROR':
            response.remove('OK')
            for msg in response:
                if ',' in msg:
                    detail = msg.split(',')
                    states.append({
                        'name': detail[0].replace('"', ''),
                        'state': int(detail[4]),
                        'state_name': MessageState(int(detail[4])).name,
                        'size': int(detail[5]),
                        'sent': int(detail[6]),
                    })
        return states
    
    def message_mo_cancel(self, name: str) -> bool:
        """Cancels a mobile-originated message in the Tx ready state."""
        response = self.atcommand(f'AT%MGRC="{name}"')
        if response[0] == 'ERROR':
            return False
        return True

    def message_mo_clear(self) -> int:
        """Clears the modem transmit queue and returns the count cancelled.
        
        Returns:
            Count of messages deleted, or -1 in case of error

        """
        list_response = self.atcommand('AT%MGRL', filter=['%MGRL:'])
        if list_response[0] == 'ERROR':
            return -1
        message_count = len(list_response)
        for msg in list_response:
            del_response = self.atcommand(f'AT%MGRD={msg}C')
            if del_response[0] == 'ERROR':
                _log.error(f'Error clearing messages from transmit queue')
                return -1
        return message_count

    def message_mt_waiting(self) -> 'list[dict]':
        """Returns a list of received mobile-terminated message information.
        
        Returns:
            List of message metadata in the receive queue including:
            - `name` (str)
            - `sin` (int) first byte of payload
            - `priority` (int)
            - `state` (int) The state number
            - `state_name` (str) The `MessageState.name`
            - `size` (int) in bytes
            - `received` (int) in bytes for large message progress

        """
        waiting = []
        response = self.atcommand('AT%MGFN', filter=['%MGFN:'])
        #: %MGFN: "name",number,priority,sin,state,length,bytes_received
        if response[0] != 'ERROR':
            response.remove('OK')
            for msg in response:
                if (',' in msg):
                    detail = msg.split(',')
                    waiting.append({
                        'name': detail[0].replace('"', ''),
                        'sin': int(detail[3]),
                        'priority': int(detail[2]),
                        'state': int(detail[4]),
                        'state_name': MessageState(int(detail[4])).name,
                        'size': int(detail[5]),
                        'received': int(detail[6])
                        })
        return waiting

    def message_mt_get(self,
                       name: str,
                       data_format: int = DataFormat.BASE64,
                       meta: bool = False,
                       ) -> 'bytes|dict':
        """Returns the payload of a specified mobile-terminated message.
        
        Payload is presented as a string with encoding based on data_format. 

        Args:
            name: The unique name in the modem queue e.g. FM01.01
            data_format: text=1, hex=2, base64=3 (default)
            meta: If False returns raw bytes, else returns formatted data
                with metadata.

        Returns:
            The raw data bytes if meta is False, or a dictionary with:
            - `name` (str) The name assigned by the modem
            - `system_message_number` (int) System-assigned number
            - `system_message_sequence` (int) System-assigned number
            - `sin` (int) First byte of payload
            - `priority` (int)
            - `state` (int) The message state number
            - `state_name` (str) The `MessageState.name`
            - `size` (int) in bytes
            - `data_format` (int) 1=text, 2=hex, 3=base64
            - `data` (str) presented based on data_format

        """
        if not meta and data_format != DataFormat.BASE64:
            data_format = DataFormat.BASE64
        response = self.atcommand(f'AT%MGFG="{name}",{data_format}')
        if response[0] == 'ERROR':
            _log.error(f'Error retrieving message {name}')
            self._handle_at_exception(response)
        #: name, number, priority, sin, state, length, data_format, data
        try:
            detail = response[0].split(',')
            sys_msg_num, sys_msg_seq = detail[1].split('.')
            msg_sin = int(detail[3])
            data_str_no_sin = detail[7]
            if data_format == DataFormat.HEX:
                data = hex(msg_sin) + data_str_no_sin.lower()
            elif data_format == DataFormat.BASE64:
                # add SIN byte to base64 blob
                databytes = bytes([msg_sin]) + b64decode(data_str_no_sin)
                if not meta:
                    return databytes
                data = b64encode(databytes).decode('ascii')
            elif data_format == DataFormat.TEXT:
                data = f'\\{msg_sin:02x}' + data_str_no_sin
            return {
                'name': detail[0].replace('"', ''),
                'system_message_number': int(sys_msg_num),
                'system_message_sequence': int(sys_msg_seq),
                'priority': int(detail[2]),
                'sin': msg_sin,
                'state': int(detail[4]),
                'state_name': MessageState(int(detail[4])).name,
                'size': int(detail[5]),
                'data_format': data_format,
                'data': data
            }
        except Exception as err:
            _log.exception(err)

    def message_mt_delete(self, name: str) -> bool:
        """Marks a Return message for deletion by the modem.
        
        Args:
            name: The unique mobile-terminated name in the queue

        Returns:
            True if the operation succeeded

        """
        response = self.atcommand(f'AT%MGFM="{name}"')
        if response[0] == 'ERROR':
            err = f' ({response[1]})' if self.error_detail else ''
            _log.error(f'Error deleting message {name}{err}')
        return response[0] == 'OK'

    @property
    def transmitter_status(self):
        response = self.atcommand('ATS54?')
        if response[0] == 'ERROR':
            self._handle_at_exception(response)
        return TransmitterStatus(int(response[0]))

    def _trace_detail(self) -> dict:
        response = self.atcommand('AT%EVMON', filter=['%EVMON:'])
        if response[0] == 'ERROR':
            self._handle_at_exception(response)
        events = response[0].split(',')
        detail = {
            'monitored': [],
            'cached': [],
        }
        for event in events:
            trace_class = int(event.split('.')[0])
            trace_subclass = int(event.split('.')[1].replace('*', ''))
            detail['monitored'].append((trace_class, trace_subclass))
            if event.endswith('*'):
                detail['cached'].append((trace_class, trace_subclass))
        return detail

    @property
    def trace_event_monitor(self) -> 'list[(int, int)]':
        return self._trace_detail()['monitored']
        
    @trace_event_monitor.setter
    def trace_event_monitor(self, events: 'list[(int, int)]'):
        command = 'AT%EVMON='
        for event in events:
            trace_class, trace_subclass = event
            if command != 'AT%EVMON=':
                command += ','
            command += f'{trace_class}.{trace_subclass}'
        response = self.atcommand(command)
        if response[0] == 'ERROR':
            self._handle_at_exception(response)

    @property
    def trace_events_cached(self) -> list:
        return self._trace_detail()['cached']

    def trace_event_get(self,
                        event: 'tuple[int, int]',
                        meta: bool = False,
                        ) -> 'str|dict':
        """Gets the cached event by class/subclass.

        NOTE: Metadata feature is experimental.

        Args:
            event: tuple of (class, subclass)
            meta: Returns the raw text string if False (default)
        
        Returns:
            String if raw is True or metadata dictionary including:
            - `data_count` (int)
            - `signed_bitmask` (str)
            - `mobile_id` (str)
            - `timestamp` (str)
            - `class` (str)
            - `subclass` (str)
            - `priority` (str)
            - `data` (str)
        
        Raises:
            AtException

        """
        def signed32(n: int) -> int:
            """Converts an integer to signed 32-bit format."""
            n = n & 0xffffffff
            return (n ^ 0x80000000) - 0x80000000
        def event_timestamp(log_timestamp: int) -> int:
            offset = int(datetime(2001, 1, 1, tzinfo=timezone.utc).timestamp())
            return log_timestamp + offset
        if not (isinstance(event, tuple) and len(event) == 2):
            raise ValueError('event_get expects (class, subclass)')
        trace_class, trace_subclass = event
        response = self.atcommand(f'AT%EVNT={trace_class},{trace_subclass}',
                                  filter=['%EVNT:'])
        #: res %EVNT: <dataCount>,<signedBitmask>,<MTID>,<timestamp>,
        # <class>,<subclass>,<priority>,<data0>,<data1>,..,<dataN>
        if response[0] == 'ERROR':
            self._handle_at_exception(response)
        if not meta:
            return response[0]
        eventdata = response[0].split(',')
        event = {
            'data_count': int(eventdata[0]),
            'signed_bitmask': bin(int(eventdata[1])),
            'timestamp': event_timestamp(int(eventdata[3])),
            'class': int(eventdata[4]),
            'subclass': int(eventdata[5]),
            'priority': int(eventdata[6]),
            'data': eventdata[7:]
        }
        iso_time = datetime.utcfromtimestamp(event['timestamp']).isoformat()
        event['isotime'] = iso_time[:19] + 'Z'
        bitmask = event['signed_bitmask'][2:]
        while len(bitmask) < event['data_count']:
            bitmask = '0' + bitmask
        for i, bit in enumerate(reversed(bitmask)):
            if bit == '1':
                event['data'][i] = signed32(int(event['data'][i]))
            else:
                event['data'][i] = int(event['data'][i])
        # TODO lookup class/subclass definitions
        for trace_def in EVENT_TRACES:
            if trace_def.trace_class != trace_class:
                continue
            if trace_def.trace_subclass != trace_subclass:
                continue
            try:
                for i, value in enumerate(event['data']):
                    tag, data_type = trace_def.data[i]
                    new_value = value
                    if 'flags' in tag and isinstance(data_type, dict):
                        new_value = []
                        for flag in data_type:
                            if flag & value:
                                new_value.append(data_type[flag])
                    elif str(tag).endswith('_state'):
                        if isinstance(data_type, dict):
                            new_value = data_type[value]
                        else:
                            try:   #: IntEnum
                                new_value = data_type(value)
                            except:
                                pass   # new_value stays as value
                    event['data'][i] = { tag: new_value }
            except Exception as err:
                _log.exception(err)
        return event

    @staticmethod
    def _list_events(bitmask: int) -> 'list[EventNotification]':
        events = []
        for notification in EventNotification:
            if bitmask & notification == notification:
                events.append(notification)
        return events

    @property
    def event_notification_monitor(self) -> 'list[EventNotification]':
        response = self.atcommand('ATS88?')
        if response[0] == 'ERROR':
            self._handle_at_exception(response)
        return self._list_events(int(response[0]))
    
    @event_notification_monitor.setter
    def event_notification_monitor(self, event_list: 'list[EventNotification]'):
        bitmask = 0
        for event in event_list:
            bitmask = bitmask | event
        response = self.atcommand(f'ATS88={bitmask}')
        if response[0] == 'ERROR':
            self._handle_at_exception(response)

    @property
    def event_notifications(self) -> 'list[EventNotification]':
        response = self.atcommand('ATS89?')
        if response[0] == 'ERROR':
            self._handle_at_exception(response)
        return self._list_events(int(response[0]))
    
    @property
    def control_state(self) -> 'int|None':
        self.satellite_status_get()
        return SatlliteControlState(self._ctrl_state)
    
    @property
    def network_status(self) -> 'str|None':
        if self._ctrl_state is None:
            self.satellite_status_get()
        return SatlliteControlState(self._ctrl_state).name

    @property
    def beamsearch_state(self) -> 'int|None':
        self.satellite_status_get()
        return BeamSearchState(self._beamsearch_state)
    
    @property
    def beamsearch(self) -> 'str|None':
        if self._beamsearch_state is None:
            self.satellite_status_get()
        return BeamSearchState(self._beamsearch_state).name

    @property
    def snr(self) -> 'float|None':
        self.satellite_status_get()
        return self._snr
            
    @property
    def satellite(self) -> 'str|None':
        if self._geo_beam_id is None:
            self.satellite_status_get()
        if self._geo_beam_id is not None:
            if self._geo_beam_id in GEOBEAMS:
                return GEOBEAMS[self._geo_beam_id].split(' ')[0]
            return f'UNDEFINED {self._geo_beam_id}'
    
    @property
    def beam_id(self) -> 'str|None':
        if self._geo_beam_id is None:
            self.satellite_status_get()
        if self._geo_beam_id is not None:
            if self._geo_beam_id in GEOBEAMS:
                return GEOBEAMS[self._geo_beam_id].split(' ')[1]
            return f'GEO{self._geo_beam_id}'
        
    def satellite_status_get(self) -> dict:
        """Returns the control state and C/No.
        
        Returns:
            Dictionary including:
            - `satellite` (str)
            - `beam_id` (str)
            - `network_status` (str)
            - `control_state` (int)
            - `beamsearch` (str)
            - `beamsearch_state` (int)
            - `snr` (float)
        
        """
        if ('sat_status' in self._holdoffs and
            int(time()) - self._holdoffs['sat_status'] < SAT_STATUS_HOLDOFF):
            _log.debug('Ignoring repeat satellite status query')
            return
        _log.debug('Querying satellite status')
        self._holdoffs['sat_status'] = int(time())
        # Trace events:
        #   Class 3 Subclass 1 C/N, Satellite Control State, Beam Search State
        #   Class 3 Subclass 5 Geo Beam ID
        command = ('ATS90=3 S91=1 S92=1 S116? S122? S123?'
                   ' S90=3 S91=5 S92=1 S102?')
        response = self.atcommand(command)
        if response[0] == 'ERROR':
            self._handle_at_exception(response)
        self._snr = round(int(response[0]) / 100.0, 2)
        self._ctrl_state = int(response[1])
        self._beamsearch_state = int(response[2])
        self._geo_beam_id = int(response[3])
        return {
            'satellite': self.satellite,
            'beam_id': self.beam_id,
            'network_status': self.network_status,
            'control_state': self._ctrl_state,
            'beamsearch': self.beamsearch,
            'beamsearch_state': self._beamsearch_state,
            'snr': self._snr,
        }

    def shutdown(self) -> bool:
        """Tell the modem to prepare for power-down."""
        _log.warning('Attempting to shut down')
        response = self.atcommand('AT%OFF')
        if response[0] == 'ERROR':
            self._handle_at_exception(response)
        return True

    def utc_time(self) -> str:
        """Returns current UTC time of the modem in ISO8601 format."""
        _log.debug('Querying system time')
        response = self.atcommand('AT%UTC', filter=['%UTC:'])
        if response[0] == 'ERROR':
            self._handle_at_exception(response)
        return response[0].replace(' ', 'T') + 'Z'

    def s_register_get(self, register: 'str|int') -> int:
        """Returns the value of the S-register requested.

        Args:
            register: The register name/number (e.g. S80)

        Returns:
            integer value or None
        """
        if isinstance(register, str):
            try:
                register = int(register.replace('S', ''))
            except ValueError:
                raise ValueError(f'Invalid S-register {register}')
        _log.debug(f'Querying S-register {register}')
        response = self.atcommand(f'ATS{register}?')
        if response[0] == 'ERROR':
            self._handle_at_exception(response)
        return int(response[0])

    def _s_registers_read(self) -> None:
        command = 'AT'
        for reg in self.s_registers:
            if command != 'AT':
                command += ' '
            command += f'{reg}?'
        response = self.atcommand(command)
        if response[0] == 'ERROR':
            _log.error('Could not read S-registers')
            raise
        index = 0
        for name, register in self.s_registers.items():
            register.value = response[index]
            index += 1

    def s_register_get_definitions(self) -> list:
        """Returns a list of S-register definitions.
        R=read-only, S=signed, V=volatile
        
        Returns:
            tuple(register, RSV, current, default, minimum, maximum) or None
        """
        raise NotImplementedError
        #: AT%SREG
        #: Sreg, RSV, CurrentVal, DefaultVal, MinimumVal, MaximumVal
        response = self.atcommand('AT%SREG')
        if response[0] == 'ERROR':
            self._handle_at_exception(response)
        response.remove('OK')
        # header_rows = response[0:1]
        # Sreg RSV CurrentVal NvmValue DefaultValue MinimumValue MaximumVal
        reg_defs = response[2:]
        registers = []
        for row in reg_defs:
            reg_def = row.split(' ')
            reg_def = tuple(filter(None, reg_def))
            registers.append(reg_def)
        return registers
