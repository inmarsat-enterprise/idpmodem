"""Library for interfacing with an IsatData Pro modem for satellite IoT."""

# Workaround for legacy async client
from idpmodem.asyncio import atcommand_async
from idpmodem.asyncio.atcommand_async import IdpModemAsyncioClient

__all__ = ['atcommand_async', 'IdpModemAsyncioClient']
