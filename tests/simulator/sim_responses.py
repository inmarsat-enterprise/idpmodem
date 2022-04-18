"""Constant responses for IDP modem simulator."""

import base64
import binascii

DELAYS_STATIC = {
    '&V': 2,
}

RESPONSES_STATIC = {
    'AT&V': '\r\nACTIVE CONFIGURATION:'
            '\r\nE1 Q0 V1 CRC=0'
            '\r\nS0:000 S3:013 S4:010 S5:008 S6:000 S7:000 S8:000 S10:000 '
            'S31:00080 S32:00025 S33:000 S34:007 S35:000 S36:00000 S37:00200 '
            'S38:001 S40:000 S41:00180 S42:65535 S50:000 S52:02500 S53:000 '
            'S60:001 S61:000 S62:001 S63:000 S64:042 S88:00000 S90:000 S91:000 ',
    
    'AT+GSN': '\r\n+GSN: 00000000MFREE3D\r\n',

    'AT+GMR': '\r\n+GMR: 3.003,3.1,8\r\n',

    'ATS39? S41? S51? S55? S56? S57?': '\r\n010\r\n\r\n00180\r\n\r\n000\r\n'
                                       '\r\n000\r\n\r\n000\r\n\r\n009\r\n',

    'ATS90=3 S91=1 S92=1 S122? S116?': '\r\n0000000010\r\n\r\n0000004093\r\n',

    'AT%MGFN': '\r\n%MGFN: "FM22.03",22.3,0,255,2,2,2\r\n'
               '"FM23.03",23.3,0,255,2,2,2\r\n'
               '"FM24.03",24.3,0,255,2,2,2\r\n'
               '"FM25.03",25.3,0,255,2,2,2\r\n'
               '"FM26.03",26.3,0,255,2,2,2\r\n'
               '"FM27.03",27.3,0,255,2,2,2\r\n'
               '"FM26.04",26.4,0,255,2,2,2\r\n',
    
    'GNSS_VALID': '\r\n%GPS: $GNRMC,221511.000,A,4517.1073,N,07550.9222,W,0.07'
                  ',0.00,150320,,,A,V*10\r\n'
                  '$GNGGA,221511.000,4517.1073,N,07550.9222,W,1,08,1.3,135.0,M'
                  ',-34.3,M,,0000*7E\r\n'
                  '$GNGSA,A,3,28,17,30,11,19,07,,,,,,,2.5,1.3,2.1,1*37\r\n'
                  '$GNGSA,A,3,87,81,,,,,,,,,,,2.5,1.3,2.1,2*32\r\n'
                  '$GPGSV,2,1,08,01,,,42,07,18,181,35,11,32,056,29,17,48,265,35'
                  ',0*5D\r\n'
                  '$GPGSV,2,2,08,19,24,256,37,28,71,317,30,30,42,209,45,51,29'
                  ',221,40,0*69\r\n'
                  '$GLGSV,1,1,04,81,22,232,36,86,00,044,,87,57,030,42,,,,37'
                  ',0*40\r\n',
                
    'GNSS_NOFIX': '\r\n%GPS: $GNRMC,014131.000,V,,,,,,,160320,,,N,V*29'
                  '\r\n$GNGGA,014131.000,,,,,0,06,2.2,,,,,,0000*48'
                  '\r\n$GNGSA,A,1,19,17,28,,,,,,,,,,4.5,2.2,3.9,1*3C\r\n'
                  '$GNGSA,A,1,81,80,79,,,,,,,,,,4.5,2.2,3.9,2*34\r\n'
                  '$GPGSV,2,1,08,02,50,263,35,06,,,38,12,,,38,17,47,104,38'
                  ',0*66\r\n'
                  '$GPGSV,2,2,08,19,68,088,30,28,11,164,41,46,33,210,37,51,29'
                  ',221,40,0*6B\r\n'
                  '$GLGSV,1,1,03,79,19,217,47,80,36,276,35,81,53,050,36'
                  ',0*4C\r\n',
}

ERROR_RESPONSES = {
    'default': '\r\n101\r\n',
    'crc': '\r\n100\r\n',
}


def nmea_get(rx_data: str):
    response = '%GPS: '
    parts = rx_data.split(',')
    for part in parts:
        if part == 'GGA':
            response += '\r\n' if response != '%GPS: ' else ''
            response += ('$GNGGA,221511.000,4517.1073,N,07550.9222,W,1,08'
                         ',1.3,135.0,M,-34.3,M,,0000*7E\r\n')
        elif part == 'RMC':
            response += '\r\n' if response != '%GPS: ' else ''
            response += ('$GNRMC,221511.000,A,4517.1073,N,07550.9222,W,0.07'
                         ',0.00,150320,,,A,V*10\r\n')
        elif part == 'GSA':
            response += '\r\n' if response != '%GPS: ' else ''
            response += ('$GNGSA,A,3,28,17,30,11,19,07,,,,,,,2.5,1.3,2.1'
                         ',1*37\r\n'
                         '$GNGSA,A,3,87,81,,,,,,,,,,,2.5,1.3,2.1,2*32\r\n')
        elif part == 'GSV':
            response += '\r\n' if response != '%GPS: ' else ''
            response += ('$GPGSV,2,1,08,01,,,42,07,18,181,35,11,32,056,29,17'
                         ',48,265,35,0*5D\r\n'
                         '$GPGSV,2,2,08,19,24,256,37,28,71,317,30,30,42,209'
                         ',45,51,29,221,40,0*69\r\n')
    return response


def mo_status_get(rx_data: str,
                  mo_message_queue: 'list[str]',
                  ) -> 'tuple[str, list[str]]':
    response = '%MGRS: '
    to_complete = []
    msg_name = None
    if '=' in rx_data:
        msg_name = rx_data.split('=')[1].replace('"', '')
    if msg_name is not None:
        response += f'\"{msg_name}\",0,0,255,2,2,2\r\n'
        to_complete.append(msg_name)
    else:
        for msg_name in mo_message_queue:
            response += f'\"{msg_name}\",0,0,255,2,2,2\r\n'
            to_complete.append(msg_name)
    return (response, to_complete)


def mt_get(rx_data: str, mt_message_queue: 'list[str]') -> 'tuple[str, str]':
    msg_name, data_format = (rx_data.split('=')[1]).split(',')
    data_format = int(data_format)
    msg_name = msg_name.replace('"', '')
    if msg_name in mt_message_queue and data_format in [1, 2, 3]:
        major, minor = msg_name.replace('FM', '').split('.')
        msg_num = '.'.join([major, str(int(minor))])
        msg_sin = 255
        msg_min = 255
        payload = b'Hello World'
        data_bytes = bytearray(
            [msg_sin, msg_min]) + bytearray(payload)
        priority = 0
        state = 2
        length = len(data_bytes)
        if data_format == 1:
            msg_data = f'\"{data_bytes.decode()}\"'
        elif data_format == 2:
            msg_data = binascii.hexlify(data_bytes)
        else:   # data_format == 3
            msg_data = base64.b64encode(data_bytes)
        return (f'\r\nAT%MGFG: \"{msg_name}\",{msg_num},{priority},'
                f'{msg_sin},{state},{length},{data_format},{msg_data}',
                msg_name)
    else:
        raise ValueError
