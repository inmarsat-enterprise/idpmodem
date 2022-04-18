# Design Considerations for the AT command module

## Key Requirements

* Attach to an IDP modem's serial port (RS232 or UART) and establish
standard communications settings
* Support (apply/validate) CRC feature for RS232 long cables
* Support standard request/response operations for relevant settings and status
queries, GNSS fix information
* Allow for unsolicited text coming from the modem e.g. upon reboot
    * Logging option
    * Callback/handler registration
* Optional filter for response prefixes e.g. `+GMM: ST` would remove `+GMM:`
* Strip whitespace leading/trailing response lines
* Optional removal of result code without using Quiet mode (i.e. validate
result but do not return code to requestor)
* Optional add error code to failed responses

### Future Considerations

* Allow *data mode* for example to support upgrading modem firmware.

## Design

### pySerial

The design iterated built upon the
[`pySerial`](https://pyserial.readthedocs.io/en/latest/pyserial_api.html)
library, based on an example AT implementation with modifications.

The pySerial `at_protocol` example is built upon successive subclasses in the
`serial.threaded` submodule to create a `protocol_factory` which is a
subclass of the `LineReader`:
```
Protocol(object)
+- Packetizer(Protocol)
  +- LineReader(Packetizer)
    +- AtProtocol(LineReader)
```
The `AtProtocol` is then passed to a `ReaderThread` along with a `Serial`
instance connected to the modem. However since the `ReaderThread` is intended
to read lines terminated by `<cr><lf>` this does not work when CRC is enabled
on the IDP modem. So we have to subclass `ReaderThread`:
```
ReaderThread(threading.Thread)
+- ByteReaderThread(ReaderThread)
```
While this is useful for generic build-up, it becomes convoluted for development
due to the loss of intellisense in the deeply nested inheritance model.
>An upcoming design iteration may combine the subclasses into a flatter
structure specific to the IDP modem AT command set.

In order to manage the dependencies between the serial instance and the
protocol factory, the **`ModemClient`** overlay exists to start and stop the
connection and processing of bytes.

### Threaded vs asyncio

Conventional wisdom suggests that I/O bound operations like talking to a modem
at 9600 baud are best handled with **async/await** type logic.
The ORBCOMM modems do queue requests, but certain requests can take a
significant amount of time - most notably GNSS/NMEA queries typically take at
least 20 seconds to resolve from cold start (sometimes much longer).
Since many applications are dependent on successive modem requests, an async
loop for the at commands is not necessarily beneficial in its own right.
The `atcommand_async` submodule should be functional to support development of
applications that benefit from interleaving modem operations with other async
operations.

Another consideration is interfacing with other third party libraries. In
particular the `PiGPIO` library is useful for using Raspberry Pi GPIO to
interact with the *notification* output of the IDP modem, but the interrupt
it triggers spawns a new Thread which can cause `asyncio` to crash unless
fronted with a non-async `Queue`.

It was also somewhat mind-bending to write async code. Initial attempts at using
the `pyserial-asyncio` library failed, and no examples quite suited. The
`aioserial` library seemed to solve the issues and produced a working design,
however as noted it had to be integrated with threaded Queues to work with
`PiGPIO`.

So at present the asyncio design has been parked in favour of threaded.

### CRC handling

The `AtProtocol` object maintains a `crc` attribute to determine whether
to apply CRC to all requests. An initial request will assume the default setting
`%CRC=0` and if a response line starts with `*`, the `crc` attribute will be
updated to apply CRC to subsequent requests. This means that
if configuring `%CRC=x` on a modem that had CRC enabled before connecting to
the modem, the first request will fail with `INVALID_CRC_SEQUENCE` but
re-issuing the same command will enable/disable CRC correctly.

### Request Queue

To allow for multi-threaded operation and avoid race conditions, a protocol
client should maintains a request queue with a depth of 1. Threads trying to
send an AT command will by default block until the prior thread's command has
completed.

### Error Code handling

Determining error codes returned by the modem requires sending a subsequent
AT command `ATS80?` to read the most recent error code.

## Observations during development

* The ORBCOMM documentation does not describe that multi-line responses such as
NMEA sentences are suffixed by `<cr><lf>` but are different from a multiple
command response where each response is prefixed *and* suffixed with `<cr><lf>`
* Setting `V0` (disable *Verbose*) does not provide meaningful benefit since
the result codes returned are only `0` (OK) or `4` (ERROR) and must be followed
with a query of `S80` to determine the specific error code if `4` is the result
