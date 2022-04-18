#!/usr/bin/env python3
#coding: utf-8
"""
Sends a periodic location and signal quality metric.

Also illustrates the message definition concept.

"""
import os
import sys
from argparse import ArgumentParser
from time import sleep, time

from idpmodem.codecs.common_mdf import (MessageCodec, MessageDefinitions,
                                        ServiceCodec, SignedIntField,
                                        UnsignedIntField)
from idpmodem.constants import MessageState
from idpmodem.location import Location
from idpmodem.threaded.modem import AtGnssTimeout, IdpModem

SERIAL_PORT = os.getenv('SERIAL_PORT', '/dev/ttyUSB0')

CODEC_SERVICE_ID = 255
CODEC_MESSAGE_IDS = {
    'mo': {
        'periodicReport': 1,
    },
    'mt': {
        'intervalSet': 1,
    }
}


class PeriodicReport(MessageCodec):
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
                         min=CODEC_MESSAGE_IDS['mo'][name],
                         description=desc)
        loc = loc or Location()
        snr = snr or 0
        # Build message bit-optimized
        ts_desc = ('{"desc": "Seconds since 1970-01-01T00:00:00Z",'
                    '"units":"seconds"}')
        self.fields.add(UnsignedIntField(name='timestamp',
                                         size=31,
                                         data_type='uint_32',
                                         description=ts_desc,
                                         value=loc.timestamp))
        lat_desc = '{"units":"degrees*60000"}'
        self.fields.add(SignedIntField(name='latitude',
                                       size=24,
                                       data_type='int_32',
                                       description=lat_desc,
                                       value=int(loc.latitude * 60000)))
        lng_desc = '{"units":"degrees*60000"}'
        self.fields.add(SignedIntField(name='longitude',
                                       size=25,
                                       data_type='int_32',
                                       description=lng_desc,
                                       value=int(loc.longitude * 60000)))
        alt_desc = '{"units":"meters"}'
        self.fields.add(SignedIntField(name='altitude',
                                       size=13,
                                       data_type='int_16',
                                       description=alt_desc,
                                       value=int(loc.altitude)))
        spd_desc = '{"units":"km/h"}'
        self.fields.add(UnsignedIntField(name='speed',
                                         size=8,
                                         data_type='uint_16',
                                         description=spd_desc,
                                         value=int(loc.speed * 1.852)))
        hdg_desc = '{"units":"degrees"}'
        self.fields.add(UnsignedIntField(name='heading',
                                         size=9,
                                         data_type='uint_16',
                                         description=hdg_desc,
                                         value=int(loc.heading)))
        self.fields.add(UnsignedIntField(name='gnssSatellites',
                                         size=4,
                                         data_type='uint_8',
                                         value=int(loc.satellites)))
        pdop_desc = '{"desc":"Probability Dilution of Precision (lower=good)"}'
        self.fields.add(UnsignedIntField(name='pdop',
                                         size=5,
                                         data_type='uint_8',
                                         description=pdop_desc,
                                         value=int(loc.pdop)))
        snr_desc = '{"units":"dBHz*10"}'
        self.fields.add(UnsignedIntField(name='snr',
                                         size=9,
                                         data_type='uint_16',
                                         description=snr_desc,
                                         value=int(snr * 10)))


class ConfigSet(MessageCodec):
    """Sets configuration properties."""
    def __init__(self, databytes: bytes = None):
        """Instantiates a message codec.
        
        Args:
            databytes (bytes): If provided, the data will be decoded
                so that message field data is populated in the codec.

        """
        name = 'configSet'
        super().__init__(name=name,
                         sin=CODEC_SERVICE_ID,
                         min=CODEC_MESSAGE_IDS['mt'][name],
                         is_forward=True)
        rpt_desc = '{"units":"seconds"}'
        self.fields.add(UnsignedIntField(name='reportInterval',
                                         size=17,
                                         data_type='uint_32',
                                         description=rpt_desc,
                                         optional=True))
        if databytes:
            self.decode(databytes)


def send_report(modem: IdpModem) -> str:
    """Submits the message to the modem transmit queue and returns a handle."""
    try:
        location = modem.location
    except AtGnssTimeout:
        print('Unable to get GNSS fix')
        return ''
    snr = modem.snr
    report = PeriodicReport(location, snr).encode()
    message_name = modem.message_mo_send(data=report['data'],
                                         data_format=report['data_format'],
                                         sin=report['sin'],
                                         min=report['min'])
    return message_name


def build_message_definition_file(filename: str):
    service = ServiceCodec(name='periodicReportingInterval',
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
    parser = ArgumentParser(description='Periodic reporting via an IDP modem.')
    parser.add_argument('-p', '--port', dest='port', type=str,
                        default=SERIAL_PORT,
                        help='the serial port of the IDP modem')
    parser.add_argument('-i', '--interval', dest='interval', type=int,
                        default=15,
                        help='the reporting interval in minutes')
    parser.add_argument('--mdf', dest='mdf', type=str,
                        help='target directory to build'
                        ' a Message Definition File')
    return vars(parser.parse_args(args=argv[1:]))


def main():
    user_options = parse_args(sys.argv)
    port = user_options['port']
    report_interval = user_options['interval']
    if user_options['mdf']:
        target_dir = user_options['mdf']
        if not os.path.isdir(target_dir):
            print(f'Warning: {target_dir} is not a valid directory'
                  ' - ignoring MDF')
        else:
            build_message_definition_file(
                f'{target_dir}/periodicReportingExample.idpmsg'
            )
    mo_queue_interval = 15   # seconds
    mo_queue = []
    mt_queue_interval = 15   # seconds
    # mt_queue = []
    report_count = 0
    print(f'>>>> Starting periodic reporting every {report_interval} minutes')
    start_time = int(time())
    try:
        modem = IdpModem(port)
        modem.connect()
        modem.config_init()
        while True:
            elapsed_time = int(time()) - start_time
            if (report_count == 0 or
                (report_interval > 0 and
                 elapsed_time % (report_interval * 60) == 0)):
                if len(mo_queue) > 0:
                    print(f'Warning: prior message still in queue')
                msg_name = send_report(modem)
                print(f'{elapsed_time}: Transmitting report ({msg_name})')
                mo_queue.append(msg_name)
                report_count += 1
            elif len(mo_queue) > 0 and elapsed_time % mo_queue_interval == 0:
                mo_statuses = modem.message_mo_state()
                for status in mo_statuses:
                    if status['state'] < MessageState.TX_COMPLETE:
                        continue
                    msg_name = status['name']
                    if msg_name in mo_queue:
                        mo_queue.remove(msg_name)
                    if status['state'] == MessageState.TX_COMPLETE:
                        print(f'{elapsed_time}: Report {msg_name} delivered')
            if elapsed_time % mt_queue_interval == 0:
                mt_message_list = modem.message_mt_waiting()
                for meta in mt_message_list:
                    if meta['sin'] != CODEC_SERVICE_ID:
                        print(f'Unrecognized MT message (SIN={meta["sin"]})')
                        continue
                    msg_name = meta['name']
                    mt_msg: bytes = modem.message_mt_get(msg_name)
                    if mt_msg[1] == CODEC_MESSAGE_IDS['mt']['intervalSet']:
                        config_message = ConfigSet(mt_msg)
                        new_interval = config_message.fields('reportInterval')
                        if new_interval >= 0 and new_interval <= 1440:
                            print(f'{elapsed_time}: Report interval updated'
                                  f' to {new_interval} minutes')
                            report_interval = new_interval
                        else:
                            print(f'Invalid interval {new_interval} minutes')
            sleep(1)
    except KeyboardInterrupt:
        print('Interrupted by user')
    finally:
        print('<<<< Stopping periodic reporting example')
        modem.disconnect()
    

if __name__ == '__main__':
    main()
