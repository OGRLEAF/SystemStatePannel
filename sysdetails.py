# coding=utf-8

import psutil
from WebSocketServer import *
import json
import socket
import time
from multiprocessing import Process
from WebSocketServer.WebSocketServer import *
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s]- %(name)s - %(message)s')
logger = logging.getLogger(__name__)


def get_details():
    cpu = psutil.cpu_times_percent()
    mem = psutil.virtual_memory()
    disk = psutil.disk_io_counters()
    net = psutil.net_io_counters()
    users = psutil.users()
    return {
        "cpu": {'count': psutil.cpu_count(), 'user': cpu.user, 'system': cpu.system},
        "mem": {'total': mem.total, 'available': mem.available, 'percent': mem.percent, 'used': mem.used},
        'disk': disk,
        'users': users,
        'net': net,
        'time': time.time()
        }


def ws_handler(conn):
    with WebSocketServer(conn, 'a') as ws:

        while True:
            if ws.state == 1:
                data = get_details()
                ws.send(bytes(json.dumps(data), encoding='utf8'))
            elif ws.state == -1:
                break
            time.sleep(1)


if __name__ == '__main__':
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('192.168.3.66', 8081))
    s.listen(1)
    logging.info('Server Started. Listening.')
    while True:
        con, addr = s.accept()
        logging.info("Accepted one. {}".format(con))
        p = Process(target=ws_handler, args=(con,))
        p.start()
