#!/usr/bin/env python3
#coding: utf-8
"""Sends a Hello World text message and optionally waits for a message to print.

To display a readable text message use the Messaging API operation
`submit_messages.json` with `RawPayload` as an array of integer bytes. For
example "Hello modem" using a SIN/MIN codec pair of 200/0 would be as follows
using the Inmarsat Messaging API v1:

{
    "accessID": "yourMailboxAccessId",
    "password": "yourMailboxPassword",
    "messages": [
        {
            "DestinationID": "yourMobileId",
            "RawPayload": [
                200,
                0,
                72,
                101,
                108,
                111,
                32,
                109,
                111,
                100,
                101,
                109
            ]
        }
    ]
}

"""
from argparse import ArgumentParser
import sys
import os
from time import sleep

from idpmodem.threaded.modem import IdpModem
from idpmodem.constants import DataFormat

SERIAL_PORT = os.getenv('SERIAL_PORT', '/dev/ttyUSB0')


def parse_args(argv: tuple) -> dict:
    """
    Parses the command line arguments.

    Args:
        argv: An array containing the command line arguments.
    
    Returns:
        A dictionary containing the command line arguments and their values.

    """
    parser = ArgumentParser(description="Hello World from an IDP modem.")
    parser.add_argument('-p', '--port',
                        dest='port',
                        type=str,
                        default=SERIAL_PORT,
                        help="the serial port of the IDP modem")
    parser.add_argument('--await-mt',
                        dest='await_mt',
                        action='store_true')
    return vars(parser.parse_args(args=argv[1:]))


def main():
    user_options = parse_args(sys.argv)
    port = user_options['port']
    await_mt = user_options['await_mt']
    mo_message_complete = False
    mt_message_received = False
    try:
        modem = IdpModem(port)
        modem.connect()
        modem.config_init()
        mo_message_id = modem.message_mo_send(data='Hello World',
                                              data_format=DataFormat.TEXT,
                                              sin=200,
                                              min=0)
        print(f'Assigned return message name: {mo_message_id}')
        while not mo_message_complete:
            sleep(5)
            return_mesage_statuses = modem.message_mo_state()
            for status in return_mesage_statuses:
                if status['name'] != mo_message_id:
                    continue
                if status['state_name'] == 'TX_COMPLETE':
                    mo_message_complete = True
                    print(f'Message {mo_message_id} delivered to cloud')
        while await_mt and not mt_message_received:
            sleep(5)
            mt_messages = modem.message_mt_waiting()
            if len(mt_messages) > 0:
                mt_message_received = True
                name = mt_messages[0]['name']
                meta = modem.message_mt_get(name, DataFormat.TEXT)
                print(f'Received: {meta["data"]}')
    except KeyboardInterrupt:
        print('Interrupted by user')
    finally:
        modem.disconnect()
    

if __name__ == '__main__':
    main()
