import os
from idpmodem import atcommand_async, IdpModemAsyncioClient

SERIAL_PORT = os.getenv('SERIAL_PORT', '/dev/ttyUSB0')

def test_import_a():
    modem = atcommand_async.IdpModemAsyncioClient(SERIAL_PORT)
    assert isinstance(modem, atcommand_async.IdpModemAsyncioClient)

def test_import_b():
    modem = IdpModemAsyncioClient(SERIAL_PORT)
    assert isinstance(modem, IdpModemAsyncioClient)
