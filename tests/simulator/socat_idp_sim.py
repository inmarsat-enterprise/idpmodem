#!/usr/bin/env python
"""A basic IDP modem simulator with predefined responses to AT commands."""

import logging
import os
import subprocess
import threading
import time

import serial

from tests.simulator.sim_responses import *

SIMDCE = os.getenv('SIMDIR', '.') + '/simdce'
SIMDTE = os.getenv('SIMDIR', '.') + '/simdte'


def socat(dte: str = SIMDTE, dce: str = SIMDCE, debug: bool = False):
    """Start a socat proxy for a given source to a given target.
    
    Args:
        dte: the name of the DTE interface to create
        dce: the name of the DCE interface to create
        debug: prints the output on exit

    """
    cmd = (f'socat -d -d -v pty,rawer,echo=0,link={dte}'
           f' pty,rawer,echo=0,link={dce}')
    process = subprocess.Popen(cmd,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               shell=True)
    stdout, stderr = process.communicate()
    # TODO: find a way to print just the tty association, not other stuff...
    if stdout and debug:
        print(f'STDOUT: {stdout}')
    if stderr and debug:
        print(f'STDERR: {stderr}')


def simulate(dte_name: str = SIMDTE, dce_name: str = SIMDCE, echo: bool = True):
    try:
        print(f'>>>> Starting IDP AT simulator: connect client to {dte_name}')
        socat_thread = threading.Thread(target=socat,
                                        args=(dte_name, dce_name),
                                        daemon=True)
        socat_thread.start()
        time.sleep(1)
        dce = serial.Serial(port=dce_name, baudrate=9600)

        def dce_write(data, delay=0):
            time.sleep(delay)
            dce.write(data.encode())

        mt_message_queue = []
        mo_message_queue = []
        ok_responses = ['AT', 'ATZ', 'AT&W']
        verbose_ok = '\r\nOK\r\n'
        verbose_error = '\r\nERROR\r\n'
        last_error = None
        rx_data: str = ''
        while dce.is_open:
            if dce.in_waiting > 0:
                char = dce.read(dce.in_waiting).decode()
                if echo:
                    dce_write(char)
                rx_data += char
                if char == '\r':
                    rx_data = rx_data.strip()
                    if rx_data.upper() == 'QUIT':
                        dce_write('Exiting...')
                        break
                    elif rx_data.upper() in ok_responses:
                        dce_write(verbose_ok)
                    elif rx_data.upper() in RESPONSES_STATIC:
                        response = RESPONSES_STATIC[rx_data.upper()]
                        if rx_data.upper() in DELAYS_STATIC:
                            delay = DELAYS_STATIC[rx_data.upper()]
                        else:
                            delay = 0
                        dce_write(response + verbose_ok, delay)
                    elif 'AT%MGFG=' in rx_data:
                        try:
                            response, name = mt_get(rx_data, mt_message_queue)
                            mt_message_queue.remove(name)
                            dce_write(response + verbose_ok)
                        except ValueError:
                            dce_write(verbose_error)
                    elif 'AT%MGFM=' in rx_data:
                        msg_name = rx_data.split('=')[1].replace('"', '')
                        if msg_name in mt_message_queue:
                            dce_write(verbose_ok)
                        else:
                            dce_write(verbose_error)
                    elif 'AT%MGRT=' in rx_data:
                        msg_name = rx_data[len('%MGRT='):].split(',')[0]
                        mo_message_queue.append(msg_name)
                        dce_write(verbose_ok)
                    elif 'AT%MGRS' in rx_data:
                        response, rem = mo_status_get(rx_data, mo_message_queue)
                        for msg in rem:
                            mo_message_queue.remove(msg)
                        dce_write(response + verbose_ok)
                    elif 'AT%GPS=' in rx_data:
                        # TODO: allow for valid fix or time out
                        response = nmea_get(rx_data)
                        dce_write(response + verbose_ok, 3)
                    elif rx_data == 'ATS80?':   # last error code
                        if last_error in ERROR_RESPONSES:
                            response = ERROR_RESPONSES[last_error]
                        else:
                            response = ERROR_RESPONSES['default']
                        dce_write(response + verbose_ok)
                    else:
                        # TODO: %CRC, %OFF, %TRK, %UTC
                        logging.warning(f'AT command {rx_data} unsupported')
                        dce_write(verbose_error)
                    rx_data = ''
    except KeyboardInterrupt:
        logging.info('Keyboard Interrupt')
    except Exception as err:
        logging.exception(err)
    finally:
        if dce and dce.is_open:
            dce.close()
        socat_thread.join()
        print('<<<< Exiting IDP AT simulator')


def loop_test():
    dte_name = SIMDTE
    dce_name = SIMDCE
    try:
        socat_thread = threading.Thread(target=socat,
                                        args=(dte_name, dce_name),
                                        daemon=True)
        socat_thread.start()
        time.sleep(1)
        dte = serial.Serial(port=dte_name, baudrate=9600)
        dce = serial.Serial(port=dce_name, baudrate=9600)
        cycles = 0
        while dte.isOpen() and dce.isOpen():
            if dce.inWaiting() > 0:
                print('\nDCE Read: {}'.format(dce.read(dce.inWaiting()).decode()))
            if cycles == 3:
                dte.write('DTE write TEST'.encode())
                cycles = 0
            cycles += 1
            time.sleep(1)
    except KeyboardInterrupt:
        print('Keyboard interrupt')
    except Exception as err:
        print(f'Error: {err}')
    finally:
        if dte and dte.is_open:
            dte.close()
        if dce and dce.is_open:
            dce.close()


if __name__ == '__main__':
    # loop_test()
    simulate()
