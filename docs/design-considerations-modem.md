# modem

## IdpModem

When developing the modem client the approach used an attempt to define
properties for the most typically used attributes of the modem.

### Messages

Messages have a historically strange assembly where the SIN (first byte)
is separated from the rest of the payload. The abstraction provided by the
`message_mo_send` and `message_mt_get` operations allow for the historical
representation to be preserved using a **`meta`** option, but by default
present a simplified chunk of `bytes` which includes SIN/MIN.

### Request Queue

To allow for multi-threaded operation and avoid race conditions, **`IdpModem`**
maintains a request queue with a depth of 1. Threads trying to send an AT
command will by default block until the prior thread's command has completed.
However there is an option to not wait, in which case a
**`ModemBusy`** error is raised if there is a message already in the queue.

### Error Code handling

Determining error codes returned by the modem requires sending a subsequent
AT command `ATS80?` to read the most recent error code. To make higher-layer
problem handling easier, the `IdpModem` by default will follow up any
`ERROR` response with a query of the error type and pass that back in the
response `list` as a second string.

This behaviour can be disabled either at creation (kwarg) or by setting the
`error_detail` attribute of the `ModemClient` to `False`.
