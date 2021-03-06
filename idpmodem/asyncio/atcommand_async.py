# -*- coding: utf-8 -*-
"""AT command protocol (asyncio) for Inmarsat IDP satellite messaging modems.

This module provides an async serial interface that sends and receives 
AT commands, decoding/abstracting typically used operations.
Based on the AioSerial package.

**WARNING**: This module needs significant refactoring and may be unstable.

Example usage::

    import asyncio
    import idpmodem

    mymodem = idpmodem.IdpModemAsyncioClient()
    initialized = asyncio.run(mymodem.initialize(crc=True))

"""

import logging
from asyncio import (AbstractEventLoop, TimeoutError, gather, get_running_loop,
                     run_coroutine_threadsafe, set_event_loop, sleep, wait_for,
                     wrap_future)
from base64 import b64decode, b64encode
from collections import OrderedDict
from glob import glob
from threading import Event, current_thread
from time import time
from typing import Tuple, Union

from aioserial import AioSerial
from idpmodem.aterror import (AtCrcConfigError, AtCrcError, AtException,
                              AtGnssTimeout, AtTimeout)
from idpmodem.constants import (AT_ERROR_CODES, CONTROL_STATES, POWER_MODES,
                                WAKEUP_PERIODS, BeamSearchState, DataFormat,
                                MessageState, TransmitterStatus)
from idpmodem.crcxmodem import get_crc, validate_crc
from idpmodem.location import Location, location_from_nmea

_log = logging.getLogger(__name__)

BAUDRATES = [2400, 4800, 9600, 19200, 38400, 57600, 115200]

NOTIFICATION_BITMASK = (
    'gnss_fix_new',
    'message_mt_received',
    'message_mo_complete',
    'network_registered',
    'modem_reset',
    'jamming_antenna_change',
    'modem_reset_pending',
    'wakeup_period_changed',
    'utc_time_set',
    'gnss_fix_timeout',
    'event_cached',
    'network_ping_acknowledged'
)


def _printable(string: str) -> str:
    """Used for visualizing non-printable AT characters."""
    return string.replace('\r', '<cr>').replace('\n', '<lf>')


def _serial_asyncio_lost_bytes(response: str) -> bool:
    """Used to capture errors in serial_asyncio.
    
    Deprecated.
    """
    if ('AT' in response or '\r\r' in response):
        return True
    return False


def _to_signed32(n):
    """Converts an integer to signed 32-bit format."""
    n = n & 0xffffffff
    return (n ^ 0x80000000) - 0x80000000


def _notifications_dict(sreg_value: int = None) -> OrderedDict:
    """Returns an OrderedDictionary as an abstracted bitmask of notifications.
    
    Args:
        sreg_value: (optional) the integer value stored in S88 or S89
    
    Returns:
        ordered dictionary corresponding to bitmask
    """
    template = OrderedDict([
        (bit, False) for bit in NOTIFICATION_BITMASK])
    if sreg_value is not None:
        bitmask = bin(int(sreg_value))[2:]
        if len(bitmask) > len(template):
            bitmask = bitmask[:len(template) - 1]
        while len(bitmask) < len(template):
            bitmask = '0' + bitmask
        i = 0
        for key in reversed(template):
            template[key] = True if bitmask[i] == '1' else False
            i += 1
    return template


class IdpModemAsyncioClient:
    """A satellite IoT messaging modem on Inmarsat's IsatData Pro service.

    **WARNING**: Deprecated

    Attributes:
        port: The serial port name e.g. `/dev/ttyUSB0`
        baudrate: The baudrate of the serial port e.g. `9600`
        crc: A boolean used if CRC-16 is enabled for long serial cables
        loop: The asyncio event loop (uses default if not provided)

    """

    def __init__(self,
                 port: str = '/dev/ttyUSB0',
                 baudrate: int = 9600,
                 loop: AbstractEventLoop = None,
                 log_verbose: bool = False,
                 ):
        """Initializes the class.
        
        Args:
            port: The serial port name e.g. `/dev/ttyUSB0`
            baudrate: The serial port baudrate
            crc: enables CRC-16 for long serial cables
            loop: (optional) external asyncio event loop to use
            logger: (optional) external logger to use
            log_level: Level for the logger to record

        """
        self._verbose = log_verbose
        self.port = port
        self.baudrate = baudrate
        self.crc = None
        self.loop = loop
        self._thread = current_thread()
        self._event = Event()
        self._serial = None
        self._pending_command = None
        self._pending_command_time = None
        self._retry_count = 0
        self._serial_async_error_count = 0

    @property
    def port(self):
        return self._port
    
    @port.setter
    def port(self, value):
        valid = len(glob(value)) == 1
        if not valid:
            err_msg = 'Serial port {} not found'.format(value)
            _log.error(err_msg)
            raise ValueError(err_msg)
        self._port = value

    @property
    def baudrate(self):
        return self._baudrate
    
    @baudrate.setter
    def baudrate(self, value):
        if value not in BAUDRATES:
            raise ValueError('Unsupported baudrate {}'.format(value))
        self._baudrate = value

    def _handle_at_error(self,
                         at_command: str,
                         err_code: Union[str, int],
                         return_value: any = None) -> any:
        """Manages log and/or raising errors.
        
        Args:
            at_command: The command that experienced an error
            err_code: The error code received
            return_value: The value to return after logging
        
        Raises:
            Re-raises the exceptions

        """
        error_str = AT_ERROR_CODES[int(err_code)]
        _log.error("{} Exception: {}".format(at_command, error_str))
        if return_value is None:
            raise AtException(error_str)
        return return_value

    async def _send(self, data: str) -> str:
        """Coroutine encodes and sends an AT command.
        
        Args:
            writer: A serial_asyncio writer
            data: An AT command string
        
        Returns:
            A string with the original data.
        """
        if self.crc:
            data = get_crc(data)
        self._pending_command = data
        to_send = self._pending_command + '\r'
        if self._verbose:
            _log.debug('Sending {}'.format(_printable(to_send)))
        self._pending_command_time = time()
        await self._serial.write_async(to_send.encode())
        return data

    async def _recv(self, timeout: int = 5) -> list:
        """Coroutine receives and decodes data from the serial port.

        Parsing stops when 'OK' or 'ERROR' is found.
        
        Args:
            reader: A serial_asyncio reader

        Returns:
            A list of response strings with empty lines removed.
        
        Raises:
            AtTimeout if the response timed out.

        """
        CRC_DELAY = 1   #: seconds after response body
        response = []
        verbose_response = ''
        msg = ''
        try:
            while True:
                chars = (await wait_for(
                    self._serial.read_until_async(b'\r\n'),
                    timeout=timeout)).decode()
                msg += chars
                verbose_response += chars
                if msg.endswith('\r\n'):
                    if self._verbose:
                        _log.debug('Processing {}'.format(_printable(msg)))
                    msg = msg.strip()
                    if msg != self._pending_command:
                        if msg != '':
                            # empty lines are not included in response list
                            # but are preserved in verbose_response for CRC
                            response.append(msg)
                    else:
                        # remove echo for possible CRC calculation
                        echo = self._pending_command + '\r'
                        if self._verbose:
                            _log.debug(f'Removing echo {_printable(echo)}')
                        verbose_response = verbose_response.replace(echo, '')
                    if msg in ['OK', 'ERROR']:
                        try:
                            response_crc = (await wait_for(
                                self._serial.read_until_async(b'\r\n'),
                                timeout=CRC_DELAY)).decode()
                            if response_crc:
                                response_crc = response_crc.strip()
                                if _serial_asyncio_lost_bytes(verbose_response):
                                    self._serial_async_error_count += 1
                                if not validate_crc(response=verbose_response,
                                                    candidate=response_crc):
                                    err_msg = '{} CRC error for {}'.format(
                                        response_crc,
                                        _printable(verbose_response))
                                    _log.error(err_msg)
                                    raise AtCrcError(err_msg)
                                elif self._verbose:
                                    _log.debug('CRC {} ok for {}'.format(
                                        response_crc,
                                        _printable(verbose_response)))
                                if not self.crc:
                                    # raise AtCrcConfigError('CRC found but unexpected') #: new <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
                                    self.crc = True
                        except TimeoutError:
                            if self.crc:
                                raise AtCrcConfigError('CRC expected but not found')   #: new <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
                            self.crc = False
                        break
                    msg = ''
        except TimeoutError:
            timeout_time = time() - self._pending_command_time
            err = ('AT timeout {} after {} seconds ({}s after command)'.format(
                self._pending_command, timeout, timeout_time))
            raise AtTimeout(err)
        return response

    async def command(self,
                      at_command: str,
                      timeout: int = 5,
                      retries: int = 0) -> list:
        """Submits an AT command and returns the response asynchronously.
        
        Proxies a private function to allow for multi-threaded operation.

        Args:
            at_command: The AT command string
            timeout: The maximum time in seconds to await a response.
            retries: Optional number of additional attempts on failure.
        
        Returns:
            A list of response strings finishing with 'OK', or 
                ['ERROR', '<error_code>']
        
        Raises:
            AtException if no response was received.
            AtException if bad CRC response count exceeds retries

        """
        if current_thread() != self._thread:
            _log.warning('Call from external thread may crash or hang')
            loop = get_running_loop()
            set_event_loop(loop)
            await sleep(1)   #: add a slight delay to mitigate race condition
            while self._event.is_set():
                pass
            concurrentfuture = run_coroutine_threadsafe(
                self._command(at_command, timeout, retries), loop)
            asyncfuture = wrap_future(concurrentfuture)
            return await asyncfuture
        else:
            return await self._command(at_command, timeout, retries)

    async def _command(self,
                       at_command: str,
                       timeout: int,
                       retries: int) -> list:
        """Submits an AT command and returns the response asynchronously.
        
        Args:
            at_command: The AT command string
            timeout: The maximum time in seconds to await a response.
            retries: Optional number of additional attempts on failure.
        
        Returns:
            A list of response strings finishing with 'OK', or 
                ['ERROR', '<error_code>']
        
        Raises:
            AtException if no response was received.
            AtException if bad CRC response count exceeds retries

        """
        try:
            self._event.set()
            try:
                if self._verbose:
                    _log.debug('Opening serial port {}'.format(self.port))
                self._serial = AioSerial(port=self.port,
                                            baudrate=self.baudrate,
                                            loop=self.loop)
            except Exception as e:
                _log.error('Error connecting to aioserial: {}'.format(e))
            try:
                if self._verbose:
                    _log.debug('Checking unsolicited data'
                               f' prior to {at_command}')
                self._pending_command_time = time()
                unsolicited = await self._recv(timeout=0.25)
                if unsolicited:
                    _log.warning('Unsolicited data: {}'.format(unsolicited))
                    # raise AtUnsolicited('Unsolicited data: {}'.format(unsolicited))
            except AtTimeout:
                if self._verbose:
                    _log.debug('No unsolicited data found')
            tasks = [self._send(at_command),
                self._recv(timeout=timeout)]
            echo, response = await gather(*tasks)
            if echo in response:
                response.remove(echo)
            if len(response) > 0:
                self._retry_count = 0
                if response[0] == 'ERROR':
                    _log.debug('AT error detected - getting reason')
                    error_code = await self.command('ATS80?')
                    if error_code is not None:
                        response.append(error_code[0])
                    else:
                        _log.error('Failed to get error_code from S80')
                return response
            raise AtException('No response received for {}'.format(at_command))
        except AtCrcError:
            self._retry_count += 1
            if self._retry_count < retries:
                _log.error('CRC error retrying')
                return await self.command(
                    at_command, timeout=timeout, retries=retries)
            else:
                error_message = 'Too many failed CRC ({})'.format(
                    self._retry_count)
                self._retry_count = 0
                raise AtException(error_message)
        finally:
            if self._serial:
                if self._verbose:
                    _log.debug('Closing serial port {}'.format(self.port))
                self._serial.close()
                self._serial = None
            self._event.clear()
    
    async def initialize(self, crc: bool = False) -> bool:
        """Initializes the modem using ATZ and sets up CRC.

        Args:
            crc: desired initial CRC enabled if True

        Returns:
            True if successful
        
        Raises:
            AtException on errors other than CRC enabled

        """
        _log.debug('Initializing modem{}'.format(
            ' (CRC enabled)' if crc else ''))
        cmd = 'ATZ;E1;V1'
        cmd += ';%CRC=1' if crc else ''
        success = await self.command(cmd)
        if success[0] == 'ERROR':
            if int(success[1]) == 100:
                if crc and self.crc:
                    _log.debug('CRC already enabled')
                    return True
                else:
                    self.crc = True
                    await self.initialize(crc)
            else:
                return self._handle_at_error(cmd, success[1], return_value=False)
        self.crc = crc
        return True
    
    async def config_restore_nvm(self) -> bool:
        """Sends the ATZ command to restore from non-volatile memory.
        
        Returns:
            Boolean success.
        """
        _log.debug('Restoring non-volatile configuration')
        cmd = 'ATZ'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1], return_value=False)
        return True

    async def config_restore_factory(self) -> bool:
        """Sends the AT&F command and returns True on success."""
        _log.debug('Restoring factory defaults')
        cmd = 'AT&F'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1], return_value=False)
        return True
    
    async def config_report(self) -> Tuple[dict, dict]:
        """Sends the AT&V command to retrive S-register settings.
        
        Returns:
            A tuple with two dictionaries or both None if failed
            at_config with booleans crc, echo, quiet and verbose
            reg_config with S-register tags and integer values

        """
        _log.debug('Querying configuration')
        cmd = 'AT&V'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1], (None, None))
        at_config = response[1]
        s_regs = response[2]
        echo, quiet, verbose, crc = at_config.split(' ')
        at_config = {
            "crc": bool(int(crc[4])),
            "echo": bool(int(echo[1])),
            "quiet": bool(int(quiet[1])),
            "verbose": bool(int(verbose[1])),
        }
        reg_config = {}
        for reg in s_regs.split(' '):
            name, value = reg.split(':')
            reg_config[name] = int(value)
        return (at_config, reg_config)

    async def config_save(self) -> bool:
        """Sends the AT&W command and returns True if successful."""
        _log.debug('Saving S-registers to non-volatile memory')
        cmd = 'AT&W'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1], False)
        return True

    async def config_crc_enable(self, crc: bool) -> bool:
        """Enables or disables CRC error checking (for long serial cable).
        
        Args:
            crc: enable CRC if true
        """
        _log.debug('{} CRC'.format('Enabling' if crc else 'Disabling'))
        cmd = 'AT%CRC={}'.format(1 if crc else 0)
        response = await self.command(cmd)
        if response[0] == 'ERROR' and self.crc != crc:
            return self._handle_at_error(cmd, response[1], False)
        self.crc = crc
        return True
    
    async def device_mobile_id(self) -> str:
        """Returns the unique Mobile ID (Inmarsat serial number).
        
        Returns:
            MobileID string.
        
        Raises:
            AtException

        """
        _log.debug('Querying device Mobile ID')
        cmd = 'AT+GSN'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            self._handle_at_error(cmd, response[1])
        return response[0].replace('+GSN:', '').strip()

    async def device_version(self) -> Tuple[str, str, str]:
        """Returns the hardware, firmware and AT versions.
        
        Returns:
            Dict with hardware, firmware, at version.
        
        Raises:
            AtException

        """
        _log.debug('Querying device version info')
        cmd = 'AT+GMR'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            self._handle_at_error(cmd, response[1])
        versions = response[0].replace('+GMR:', '').strip()
        fw_ver, hw_ver, at_ver = versions.split(',')
        return {'hardware': hw_ver, 'firmware': fw_ver, 'at': at_ver}

    async def gnss_continuous_set(self,
                                  interval: int=0,
                                  doppler: bool=True) -> bool:
        """Sets the GNSS continous mode (0 = on-demand).
        
        Args:
            interval: Seconds between GNSS refresh.
            doppler: Often required for moving assets.
        
        Returns:
            True if successful setting.

        """
        _log.debug('Setting GNSS refresh to {} seconds'.format(interval))
        cmd = 'AT%TRK={}{}'.format(interval, ',{}'.format(1 if doppler else 0))
        if interval < 0 or interval > 30:
            raise ValueError('GNSS continuous interval must be in range 0..30')
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1], False)
        return True

    async def gnss_nmea_get(self,
                            stale_secs: int = 1,
                            wait_secs: int = 35,
                            sentences: list = ['RMC', 'GSA', 'GGA', 'GSV']
                            ) -> Union[list, str]:
        """Returns a list of NMEA-formatted sentences from GNSS.

        Args:
            stale_secs: Maximum age of fix in seconds (1..600)
            wait_secs: Maximum time to wait for fix (1..600)
            sentences: Optional list of NMEA sentence types to get

        Returns:
            List of NMEA sentences

        Raises:
            ValueError if parameter out of range
            AtGnssTimeout if no response from GNSS
            AtException

        """
        _log.debug('Requesting GNSS fix information')
        NMEA_SUPPORTED = ['RMC', 'GGA', 'GSA', 'GSV']
        BUFFER_SECONDS = 5
        if (stale_secs not in range(1, 600+1) or
            wait_secs not in range(1, 600+1)):
            raise ValueError('stale_secs and wait_secs must be 1..600')
        sentence_list = ''
        for sentence in sentences:
            sentence = sentence.upper()
            if sentence in NMEA_SUPPORTED:
                if len(sentence_list) > 0:
                    sentence_list += ','
                sentence_list += '"{}"'.format(sentence)
            else:
                raise ValueError('Unsupported NMEA sentence: {}'
                                 .format(sentence))
        cmd = 'AT%GPS={},{},{}'.format(stale_secs, wait_secs, sentence_list)
        response = await self.command(cmd, timeout=wait_secs + BUFFER_SECONDS)
        if response[0] == 'ERROR':
            if int(response[1]) == 108:
                raise AtGnssTimeout('Timed out waiting for GNSS fix')
            else:
                return self._handle_at_error(cmd, response[1], None)
        if 'OK' in response:
            response.remove('OK')
        response[0] = response[0].replace('%GPS: ', '')
        return response

    async def location(self,
                       stale_secs: int = 1,
                       wait_secs: int = 35) -> Location:
        """Returns a location object.
        
        Args:
            stale_secs: the maximum fix age to accept
            wait_secs: the maximum time to wait for a new fix
        
        Returns:
            nmea.Location object
        
        Raises:
            AtGnssTimeout if no location data is available
        
        """
        _log.debug('Querying location')
        nmea_sentences = await self.gnss_nmea_get(stale_secs, wait_secs)
        return location_from_nmea(nmea_sentences)

    async def lowpower_mode_set(self, power_mode: int) -> bool:
        """Sets the modem power mode (for blockage recovery).

        Args:
            power_mode (int): The new power mode

        Returns:
            True if successful
        
        Raises:
            ValueError on invalid power_mode
        """
        if power_mode not in POWER_MODES:
            raise ValueError('Invalid power mode {}'.format(power_mode))
        _log.debug('Setting power mode {}'.format(
            POWER_MODES[power_mode]))
        cmd = 'ATS50={}'.format(power_mode)
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1], False)
        return True

    async def lowpower_mode_get(self) -> int:
        """Gets the modem power mode.

        Returns:
            The integer value of the power mode
        
        Raises:
            AtException if an error was returned

        """
        _log.debug('Getting power mode')
        cmd = 'ATS50?'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1], None)
        return int(response[0])

    async def lowpower_wakeup_set(self, wakeup_period: int) -> bool:
        """Sets the modem wakeup period.

        Args:
            wakeup_period (int): The new wakeup period

        Returns:
            True if successful
        
        Raises:
            ValueError on invalid wakeup_period

        """
        if wakeup_period not in WAKEUP_PERIODS:
            raise ValueError('Invalid wakeup period {}'.format(wakeup_period))
        _log.debug('Setting wakeup period {}'.format(
            WAKEUP_PERIODS[wakeup_period]))
        cmd = 'ATS51={}'.format(wakeup_period)
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1], False)
        return True

    async def lowpower_wakeup_get(self) -> int:
        """Gets the modem wakeup period.

        Returns:
            The integer value of the wakeup period
        
        Raises:
            AtException if an error was returned

        """
        _log.debug('Getting wakeup period')
        cmd = 'ATS51?'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1], None)
        return int(response[0])

    async def lowpower_notifications_enable(self) -> bool:
        """Configures low power satellite status and notification assertion.

        The following events trigger assertion of the notification output:
        - New Forward Message received
        - Return Message completed (success or failure)
        - Trace event update (satellite status change)

        Returns:
            True if successful
        """
        _log.debug('Enabling low power notifications')
        cmd = 'AT%EVMON=3.1;S88=1030'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1], False)
        return True

    async def lowpower_notifications_check(self) -> list:
        """Returns a list of relevant events."""
        _log.debug('Querying low power notifications')
        relevant = []
        try:
            reason = await self.notification_check()
            if reason is not None:
                if reason['event_cached'] == True:
                    relevant.append('event_cached')
                if reason['message_mt_received'] == True:
                    relevant.append('message_mt_received')
                if reason['message_mo_complete'] == True:
                    relevant.append('message_mo_complete')
        except AtException:
            _log.warning('Notification check returned AT exception')
        finally:
            return relevant

    async def message_mo_send(self,
                              data: str,
                              data_format: int,
                              sin: int,
                              min: int = None,
                              name: str = None,
                              priority: int = 4) -> str:
        """Submits a mobile-originated message to send.
        
        Args:
            data: The data to be sent formatted as base64, hex or text according
                to `data_format`.
            data_format: 1: Text, 2: ASCII-Hex, 3: Base64 (MIME)
            name: (Optional) A unique name for the message, if none is provided
                a name based on unix timestamp will be assigned
            priority: 1: High .. 4: Low (default)
            sin: Service Identification Number (15..255) becomes the first byte
                of message payload
            min: (Optional) Message Identification Number (0..255) becomes the
                second byte of message payload if specified

        Returns:
            Name of the message if successful, or the error string
        """
        _log.debug('Submitting message named {}'.format(name))
        if name is None:
            # Use the 8 least-signficant numbers of unix timestamp as unique
            name = str(int(time()))[-8:]
            _log.debug('Assigned name {}'.format(name))
        elif len(name) > 8:
            name = name[0:8]   # risk duplicates create an ERROR resposne
            _log.warning('Truncated name to {}'.format(name))
        _min = '.{}'.format(min) if min is not None else ''
        if data_format == 1:
            data = '"{}"'.format(data)
        cmd = ('AT%MGRT="{}",{},{}{},{},{}'.format(name,
                                                    priority,
                                                    sin,
                                                    _min,
                                                    data_format,
                                                    data))
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1], None)
        return name

    async def message_mo_state(self, name: str = None) -> list:
        """Returns the message state(s) requested.
        
        If no name filter is passed in, all available messages states
        are returned.  Returns False is the request failed.

        Args:
            name: The unique message name in the modem queue

        Returns:
            `list` of `dict` with `name`, `state`, `size` and `sent`

        Raises:
            AtException

        """
        _log.debug('Querying transmit message state{}'.format(
            ' ={}'.format(name) if name else 's'))
        cmd = 'AT%MGRS{}'.format('="{}"'.format(name) if name else '')
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1], None)
        # %MGRS: "<name>",<msg_no>,<priority>,<sin>,<state>,<size>,<sent_bytes>
        if 'OK' in response:
            response.remove('OK')
        states = []
        for res in response:
            res = res.replace('%MGRS:', '').strip()
            if len(res) > 0:
                name, number, priority, sin, state, size, sent = res.split(',')
                del number
                del priority
                del sin
                states.append({
                    'name': name.replace('"', ''),
                    'state': int(state),
                    'size': int(size),
                    'bytes_sent': int(sent),
                    })
        return states
    
    @staticmethod
    def message_state_name(state: int):
        return MessageState(state).name

    async def message_mo_cancel(self, name: str) -> bool:
        """Cancels a mobile-originated message in the Tx ready state."""
        _log.debug('Cancelling message {}'.format(name))
        cmd = 'AT%MGRC="{}"'.format(name)
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1], False)
        return True

    async def message_mo_clear(self) -> int:
        """Clears the modem transmit queue.
        
        Returns:
            Count of messages deleted
        
        Raises:
            AtException

        """
        _log.debug('Clearing transmit queue of return messages')
        cancelled_count = 0
        open_count = 0
        cmd = 'AT%MGRS'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1])
        if 'OK' in response:
            response.remove('OK')
        if '%MGRS:' in response:
            response.remove('%MGRS:')
        for message in response:
            if '%MGRS:' in message:
                message = message.replace('%MGRS:', '').strip()
            parts = message.split(',')
            status = int(parts[4])
            name = parts[0].replace('"', '')
            if status < 6:
                cancel_explicit = await self.message_mo_cancel(name)
                if not cancel_explicit:
                    open_count += 1
                else:
                    cancelled_count += 1
        if open_count > 0:
            _log.warning('{} messages still in transmit queue'.format(
                open_count))
        return cancelled_count

    async def message_mt_waiting(self) -> list:
        """Returns a list of received mobile-terminated message information.
        
        Returns:
            List of (name, number, priority, sin, state, length, received)
        
        Raises:
            AtException

        """
        _log.debug('Checking receive queue for forward messages')
        cmd = 'AT%MGFN'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1])
        if 'OK' in response:
            response.remove('OK')
        waiting = []
        #: %MGFN: name, number, priority, sin, state, length, bytes_received
        for res in response:
            msg = res.replace('%MGFN:', '').strip()
            if msg.startswith('"FM'):
                parts = msg.split(',')
                name, number, priority, sin, state, length, received = parts
                del number   #: unused
                waiting.append({'name': name.replace('"', ''),
                                'sin': int(sin),
                                'priority': int(priority),
                                'state': int(state),
                                'length': int(length),
                                'received': int(received)})
        return waiting

    @staticmethod
    def _message_mt_parse(mgfg_response: str,
                          data_format: int) -> dict:
        #:%MGFG:"<msgName>",<msgNum>,<priority>,<sin>,<state>,<length>,<data_format>,<data>
        parts = mgfg_response.replace('%MGFG:', '').strip().split(',')
        sys_msg_num, sys_msg_seq = parts[1].split('.')
        msg_sin = int(parts[3])
        data_str_no_sin = parts[7]
        if data_format == DataFormat.HEX:
            data = '{:02X}'.format(msg_sin) + data_str_no_sin
            databytes = bytes.fromhex(data)
        elif data_format == DataFormat.BASE64:
            databytes = bytes([msg_sin]) + b64decode(data_str_no_sin)
            data = b64encode(databytes).decode('ascii')
        elif data_format == DataFormat.TEXT:
            data_str_no_sin = data_str_no_sin[1:len(data_str_no_sin) - 1]
            data = '\\{:02x}'.format(msg_sin) + data_str_no_sin
            databytes = bytes([msg_sin])
            i = 0
            while i < len(data_str_no_sin):
                if data_str_no_sin[i] == '\\' and i < len(data_str_no_sin) - 1:
                    if data_str_no_sin[i + 1] in '0123456789ABCDEF':
                        databytes += bytes([int(data_str_no_sin[i+1:i+3], 16)])
                        i += 3
                else:
                    databytes += data_str_no_sin[i].encode('utf-8')
                    i += 1
        return {
            'name': parts[0].replace('"', ''),
            'system_message_number': int(sys_msg_num),
            'system_message_sequence': int(sys_msg_seq),
            'priority': int(parts[2]),
            'sin': msg_sin,
            'min': databytes[1],
            'state': int(parts[4]),
            'length': int(parts[5]),
            'data_format': data_format,
            'raw_payload': data,
            'bytes': databytes,
        }

    async def message_mt_get(self,
                             name: str,
                             data_format: int = DataFormat.BASE64,
                             verbose: bool = True) -> Union[dict, bytes]:
        """Returns the payload of a specified mobile-terminated message.
        
        Payload is presented as a string with encoding based on data_format. 

        Args:
            name: The unique name in the modem queue e.g. FM01.01
            data_format: text=1, hex=2, base64=3 (default)
            verbose: if True returns a dictionary, otherwise raw payload bytes

        Returns:
            The encoded data as a string
        
        Raises:
            AtException

        """
        _log.debug('Retrieving forward message {}'.format(name))
        cmd = 'AT%MGFG="{}",{}'.format(name, data_format)
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1])
        message = self._message_mt_parse(response[0], data_format=data_format)
        return message if verbose else message['bytes']

    async def message_mt_delete(self, name: str) -> bool:
        """Marks a Return message for deletion by the modem.
        
        Args:
            name: The unique mobile-terminated name in the queue

        Returns:
            True if the operation succeeded

        """
        _log.debug('Marking forward message {} for deletion'.format(name))
        cmd = 'AT%MGFM="{}"'.format(name)
        try:
            response = await self.command(cmd)
            if response[0] == 'ERROR':
                return self._handle_at_error(cmd, response[1], False)
            return True
        except:
            return False

    async def event_monitor_get(self) -> list:
        """Returns a list of monitored/cached events.
        As a list of <class.subclass> strings which includes an asterisk
        for each new event that can be retrieved.

        Returns:
            list of strings <class.subclass[*]> or None
        
        Raises:
            AtException

        """
        _log.debug('Querying monitored events')
        cmd = 'AT%EVMON'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1])
        events = response[0].replace('%EVMON: ', '').split(',')
        '''
        for i in range(len(events)):
            c, s = events[i].strip().split('.')
            if s[-1] == '*':
                s = s.replace('*', '')
                # TODO flag change for retrieval
            events[i] = (int(c), int(s))
        '''
        return [event for event in events if event != '']

    async def event_monitor_set(self, eventlist: list) -> bool:
        """Sets trace events to monitor.

        Args:
            eventlist: list of tuples (class, subclass)

        Returns:
            True if successfully set

        """
        _log.debug('Setting event monitors: {}'.format(eventlist))
        #: AT%EVMON{ = <c1.s1>[, <c2.s2> ..]}
        cmd = 'AT%EVMON='
        if eventlist is not None:
            for monitor in eventlist:
                if isinstance(monitor, tuple):
                    if len(cmd) > 9:
                        cmd += ','
                    cmd += '{}.{}'.format(monitor[0], monitor[1])
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1], False)
        return True

    async def event_get(self,
                        event: tuple,
                        raw: bool = True) -> Union[str, dict]:
        """Gets the cached event by class/subclass.

        Args:
            event: tuple of (class, subclass)
            raw: Returns the raw text string if True
        
        Returns:
            String if raw=True, dictionary if raw=False
        
        Raises:
            AtException

        """
        _log.debug('Querying events: {}'.format(event))
        #: AT%EVNT=c,s
        #: res %EVNT: <dataCount>,<signedBitmask>,<MTID>,<timestamp>,
        # <class>,<subclass>,<priority>,<data0>,<data1>,..,<dataN>
        if not (isinstance(event, tuple) and len(event) == 2):
            raise AtException('event_get expects (class, subclass)')
        cmd = 'AT%EVNT={},{}'.format(event[0], event[1])
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1])
        eventdata = response[0].replace('%EVNT: ', '').split(',')
        event = {
            'data_count': int(eventdata[0]),
            'signed_bitmask': bin(int(eventdata[1]))[2:],
            'mobile_id': eventdata[2],
            'timestamp': eventdata[3],
            'class': eventdata[4],
            'subclass': eventdata[5],
            'priority': eventdata[6],
            'data': eventdata[7:]
        }
        bitmask = event['signed_bitmask']
        while len(bitmask) < event['data_count']:
            bitmask = '0' + bitmask
        i = 0
        for bit in reversed(bitmask):
            #: 32-bit signed conversion redundant since response is string
            if bit == '1':
                event['data'][i] = _to_signed32(int(event['data'][i]))
            else:
                event['data'][i] = int(event['data'][i])
            i += 1
        # TODO lookup class/subclass definitions
        return response[0] if raw else event

    async def notification_control_set(self, event_map: list) -> bool:
        """Sets the event notification bitmask.

        Args:
            event_map: list of tuples (event_name, bool)
        
        Returns:
            True if successful.
            
        """
        _log.debug('Setting event notifications: {}'.format(event_map))
        #: ATS88=bitmask
        notifications_changed = False
        old_notifications = await self.notification_control_get()
        if old_notifications is None:
            return False
        bitmask = list('0' * len(old_notifications))
        i = 0
        for event in event_map:
            if event[0] not in NOTIFICATION_BITMASK:
                raise ValueError('Invalid event {}'.format(event[0]))
            i = 0
            for key in reversed(old_notifications):
                bit = '1' if old_notifications[key] or bitmask[i] == '1' else '0'
                if key == event[0]:
                    notify = event[1]
                    if old_notifications[key] != notify:
                        bit = '1' if notify else '0'
                        notifications_changed = True
                        # self.notifications[key] = notify
                bitmask[i] = bit
                i += 1
        if notifications_changed:
            cmd = 'ATS88={}'.format(int('0b' + ''.join(bitmask), 2))
            response = await self.command(cmd)
            if response[0] == 'ERROR':
                return self._handle_at_error(cmd, response[1], False)
        return True
    
    async def notification_control_get(self) -> OrderedDict:
        """Returns the current notification configuration bitmask.
        
        Returns:
            OrderedDict
        
        Raises:
            AtException

        """
        _log.debug('Querying event notification controls')
        cmd =  'ATS88?'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1])
        return _notifications_dict(int(response[0]))

    async def notification_check(self) -> OrderedDict:
        """Returns the current active event notification bitmask (S89).
        
        The value of S89 register is cleared upon reading.

        Returns:
            OrderedDict
        
        Raises:
            AtException

        """
        _log.debug('Querying event notification triggers')
        cmd = 'ATS89?'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1])
        return _notifications_dict(int(response[0]))

    async def satellite_status(self) -> dict:
        """Returns the control state and C/No.
        
        Returns:
            Dictionary with state (int), snr (float), beamsearch (int),
                state_name (str), beamsearch_name (str), or None if error.

        Raises:
            AtException

        """
        _log.debug('Querying satellite status/SNR')
        cmd = 'ATS90=3 S91=1 S92=1 S116? S122? S123?'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1])
        if 'OK' in response:
            response.remove('OK')
        cn_0, ctrl_state, beamsearch_state = response
        cn_0 = int(cn_0) / 100.0
        ctrl_state = int(ctrl_state)
        beamsearch_state = int(beamsearch_state)
        return {
            'state': ctrl_state,
            'state_name': CONTROL_STATES[ctrl_state],
            'snr': cn_0,
            'beamsearch': beamsearch_state,
            'beamsearch_name': BeamSearchState(beamsearch_state).name,
        }

    @staticmethod
    def sat_status_name(ctrl_state: int) -> str:
        """Returns human-readable definition of a control state value.
        
        Raises:
            ValueError if ctrl_state is not found.
        """
        if ctrl_state not in CONTROL_STATES:
            raise ValueError('Control state {} not found'.format(ctrl_state))
        return CONTROL_STATES[ctrl_state]

    @staticmethod
    def sat_beamsearch_name(beamsearch_state: int) -> str:
        return BeamSearchState(beamsearch_state).name

    async def transmit_status(self) -> dict:
        """Returns the transmitter status.
        
        Returns:
            Transmit status (5 = OK)

        Raises:
            AtException if error returned by modem

        """
        _log.debug('Querying transmitter status')
        cmd = 'ATS54?'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1])
        status = int(response[0])
        return TransmitterStatus(status)

    async def shutdown(self) -> bool:
        """Tell the modem to prepare for power-down."""
        _log.debug('Requesting power down')
        cmd = 'AT%OFF'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1], False)
        return True

    async def time_utc(self) -> str:
        """Returns current UTC time of the modem in ISO format.
        
        Returns:
            UTC as ISO-formatted string
        
        Raises:
            AtException

        """
        _log.debug('Requesting UTC network time')
        cmd = 'AT%UTC'
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1])
        return response[0].replace('%UTC: ', '').replace(' ', 'T') + 'Z'

    async def s_register_get(self, register: int) -> Union[int, None]:
        """Returns the value of the S-register requested.

        Args:
            register: The S-register number

        Returns:
            integer value of register
        
        Raises:
            AtException

        """
        _log.debug('Querying register value S{}'.format(register))
        cmd = 'ATS{}?'.format(register)
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[1])
        return int(response[0])

    async def s_register_get_all(self) -> list:
        """Returns a list of S-register definitions.
        R=read-only, S=signed, V=volatile
        
        Returns:
            tuple(register, RSV, current, default, minimum, maximum)
        
        Raises:
            AtException

        """
        _log.debug('Querying S-register values')
        cmd = 'AT%SREG'
        #: Sreg, RSV, CurrentVal, DefaultVal, MinimumVal, MaximumVal
        response = await self.command(cmd)
        if response[0] == 'ERROR':
            return self._handle_at_error(cmd, response[0])
        if 'OK' in response:
            response.remove('OK')
        reg_defs = response[2:]
        registers = []
        for row in reg_defs:
            reg_def = row.split(' ')
            reg_def = tuple(filter(None, reg_def))
            registers.append(reg_def)
        return registers
