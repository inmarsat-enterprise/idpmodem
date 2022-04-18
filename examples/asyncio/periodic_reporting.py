#!/usr/bin/env python3
#coding: utf-8
"""
Sends a periodic location and signal quality metric.

Also illustrates the message definition concept.

"""
import asyncio
from argparse import ArgumentParser
import sys
from time import sleep, time

from idpmodem.asyncio.atcommand_async import IdpModemAsyncioClient, AtGnssTimeout
from idpmodem.constants import DataFormat
from idpmodem.codecs.common_mdf import Service, Message, UnsignedIntField, SignedIntField, MessageDefinitions
from idpmodem.location import Location 

CODEC_SERVICE_ID = 255
CODEC_MESSAGE_IDS = {
    'return': {
        'periodicReport': 1,
    },
    'forward': {
        'intervalSet': 1,
    }
}


class PeriodicReport(Message):
    """The periodic report sent with location and SNR."""
    def __init__(self,
                 loc: Location,
                 snr: float):
        """Create a PeriodicReport.
        
        Args:
            loc: The location to send
            snr: The signal level to send

        """
        name = 'periodicReport'
        desc = ('Contains location and SNR information'
                'reported at a configurable interval.')
        super().__init__(name=name,
                         sin=CODEC_SERVICE_ID,
                         min=CODEC_MESSAGE_IDS['return'][name],
                         description=desc)
        if loc is None:
            loc = Location()
        if snr is None:
            snr = 0
        # Build message bit-optimized
        ts_desc = ('{"desc": "Seconds since 1970-Jan-1 00:00:00",'
                    '"units":"seconds"}')
        self.fields.add(UnsignedIntField(
            name='timestamp',
            size=31,
            data_type='uint_32',
            description=ts_desc,
            value=loc.timestamp)
        )
        lat_desc = '{"units":"degrees*60000"}'
        self.fields.add(SignedIntField(
            name='latitude',
            size=24,
            data_type='int_32',
            description=lat_desc,
            value=int(loc.latitude * 60000))
        )
        lng_desc = '{"units":"degrees*60000"}'
        self.fields.add(SignedIntField(
            name='longitude',
            size=25,
            data_type='int_32',
            description=lng_desc,
            value=int(loc.longitude * 60000))
        )
        alt_desc = '{"units":"meters"}'
        self.fields.add(SignedIntField(
            name='altitude',
            size=13,
            data_type='int_16',
            description=alt_desc,
            value=int(loc.altitude))
        )
        spd_desc = '{"units":"km/h"}'
        self.fields.add(UnsignedIntField(
            name='speed',
            size=8,
            data_type='uint_16',
            description=spd_desc,
            value=int(loc.speed * 1.852))
        )
        hdg_desc = '{"units":"degrees"}'
        self.fields.add(UnsignedIntField(
            name='heading',
            size=9,
            data_type='uint_16',
            description=hdg_desc,
            value=int(loc.heading))
        )
        self.fields.add(UnsignedIntField(
            name='gnssSatellites',
            size=4,
            data_type='uint_8',
            value=int(loc.satellites))
        )
        pdop_desc = '{"desc":"Probability Dilution of Precision (lower=good)"}'
        self.fields.add(UnsignedIntField(
            name='pdop',
            size=5,
            data_type='uint_8',
            description=pdop_desc,
            value=int(loc.pdop))
        )
        snr_desc = '{"units":"dBHz*10"}'
        self.fields.add(UnsignedIntField(
            name='snr',
            size=9,
            data_type='uint_16',
            description=snr_desc,
            value=int(snr * 10))
        )


class ConfigSet(Message):
    """Sets configuration properties."""
    def __init__(self, databytes: bytes = None):
        name = 'configSet'
        super().__init__(name=name,
                         sin=CODEC_SERVICE_ID,
                         min=CODEC_MESSAGE_IDS['forward'][name],
                         is_forward=True)
        rpt_desc = '{"units":"seconds"}'
        self.fields.add(UnsignedIntField(
            name='reportInterval',
            size=17,
            data_type='uint_32',
            description=rpt_desc,
            optional=True)
        )
        if databytes:
            self.decode(databytes)


def send_report(modem: IdpModemAsyncioClient) -> str:
    try:
        location = asyncio.run(modem.location())
    except AtGnssTimeout:
        print('Unable to get GNSS fix')
        return ''
    snr = asyncio.run(modem.satellite_status())['snr']
    report = PeriodicReport(location, snr).encode()
    message_name = asyncio.run(modem.message_mo_send(
        data=report['data'],
        data_format=report['data_format'],
        sin=report['sin'],
        min=report['min'],
    ))
    return message_name


def process_command(modem: IdpModemAsyncioClient, message_name: str) -> dict:
    result = {}
    message = asyncio.run(modem.message_mt_get(message_name, DataFormat.HEX))
    if message['sin'] != CODEC_SERVICE_ID:
        print(f'Unrecognized message SIN {message["sin"]} received - ignoring')
        return
    if message['min'] == CODEC_MESSAGE_IDS['forward']['intervalSet']:
        config_message: Message = ConfigSet(message['bytes'])
        new_interval = config_message.fields('reportInterval')
        if new_interval < 0:
            print(f'Invalid interval {new_interval} minutes')
        else:
            result['interval'] = new_interval
    return result


def build_message_definition_file(filename: str):
    service = Service(name='periodicReportingInterval',
                      sin=CODEC_SERVICE_ID,
                      description='A proof of concept application')
    service.messages_return.add(PeriodicReport(None, None))
    service.messages_forward.add(ConfigSet())
    mdf = MessageDefinitions()
    mdf.services.add(service)
    mdf.mdf_export(filename, pretty=True)


def parse_args(argv: tuple) -> dict:
    """
    Parses the command line arguments.

    Args:
        argv: An array containing the command line arguments.
    
    Returns:
        A dictionary containing the command line arguments and their values.

    """
    parser = ArgumentParser(description="Periodic reporting via an IDP modem.")
    parser.add_argument('-p', '--port', dest='port', type=str,
                        default='/dev/tty.usbserial-3',
                        help="the serial port of the IDP modem")
    parser.add_argument('-i', '--interval', dest='interval', type=int,
                        default=15,
                        help="the reporting interval in minutes")
    parser.add_argument('--mdf', dest='mdf', action='store_true',
                        help="build the Message Definition File")
    return vars(parser.parse_args(args=argv[1:]))


def main():
    user_options = parse_args(sys.argv)
    port = user_options['port']
    report_interval = user_options['interval']
    if user_options['mdf']:
        build_message_definition_file('$HOME/periodicReportingExample.idpmsg')
    mo_queue_interval = 15
    mt_queue_interval = 15
    message_count = 0
    start_time = time()
    report_queued = None
    try:
        modem = IdpModemAsyncioClient(port=port)
        while True:
            elapsed_seconds = round(time() - start_time, 0)
            if (report_interval > 0 and
                elapsed_seconds >= report_interval * 60 or message_count == 0):
                if not report_queued:
                    report_queued = send_report(modem)
                    message_count += 1
                else:
                    print(f'Prior report {report_queued} pending')
                start_time = time()
            elif report_queued and elapsed_seconds % mo_queue_interval == 0:
                return_mesage_statuses = asyncio.run(modem.message_mo_state())
                # below is not best practice, should iterate statuses and
                # confirm state as delivered. here we oversimplify that once
                # de-queued it was delivered
                if len(return_mesage_statuses) == 0:
                    print(f'Report {report_queued} delivered to cloud')
                    report_queued = None
            elif elapsed_seconds % mt_queue_interval == 0:
                forward_messages = asyncio.run(modem.message_mt_waiting())
                if len(forward_messages) > 0:
                    for forward_message in forward_messages:
                        result = process_command(modem, forward_message['name'])
                        if 'interval' in result:
                            report_interval = result['interval']
            sleep(1)
    
    except KeyboardInterrupt:
        print('Interrupted by user')
    

if __name__ == '__main__':
    main()
