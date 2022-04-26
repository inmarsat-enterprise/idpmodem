from idpmodem.crcxmodem import get_crc, validate_crc


def test_crc():
    command = 'ATS80?'
    command_with_crc = get_crc(command)
    crc = command_with_crc.split('*')[1]
    valid = validate_crc(f'{command}', f'*{crc}')
    assert valid
