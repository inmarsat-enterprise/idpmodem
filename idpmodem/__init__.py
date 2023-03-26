"""Library for interfacing with an IsatData Pro modem for satellite IoT."""
__version__ = '2.3.5'

# Workaround for legacy async client
from idpmodem.asyncio import atcommand_async
from idpmodem.asyncio.atcommand_async import IdpModemAsyncioClient

__all__ = ['atcommand_async', 'IdpModemAsyncioClient']
