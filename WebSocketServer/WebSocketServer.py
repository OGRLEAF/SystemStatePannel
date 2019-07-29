# coding=utf-8
import time
import hashlib
import base64
import struct
from ServerExceptions import *
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s]- %(name)s - %(message)s')
logger = logging.getLogger(__name__)

HTTP_RESPONSE = "HTTP/1.1 {code} {msg}\r\n"  \
                "Server:LyricTool\r\n" \
                "Date:{date}\r\n" \
                "Content-Length:{length}\r\n" \
                "\r\n" \
                "{content}\r\n"
STATUS_CODE = {200: 'OK', 501: 'Not Implemented'}
UPGRADE_WS = "HTTP/1.1 101 Switching Protocols\r\n" \
             "Connection: Upgrade\r\n" \
             "Upgrade: websocket\r\n" \
             "Sec-WebSocket-Accept: {}\r\n" \
             "WebSocket-Protocol: chat\r\n\r\n"


def sec_key_gen(msg):
    key = msg + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
    ser_key = hashlib.sha1(key.encode('utf-8')).digest()
    return base64.b64encode(ser_key).decode()


class WebSocketServer:
    # Websocket操作码 opcode
    FRAME_CONTINUATION = 0x00
    FRAME_TEXT = 0x01
    FRAME_BINARY = 0x02
    FRAME_CLOSE = 0x08
    FRAME_PING = 0x09
    FRAME_PONG = 0x0A

    # 支持的Websocket关闭状态码
    CLOSE_NORMAL = 1000
    CLOSE_GOING_AWAY = 1001
    CLOSE_PROTOCOL_ERROR = 1002
    CLOSE_UNSUPPORTED = 1003
    CLOSE_NO_STATUS = 1005
    CLOSE_ABNORMAL = 1006
    UNSUPPORTED_DATA = 1007
    POLICY_VIOLATION = 1008
    CLOSE_TOO_LARGE = 1009
    INTERNAL_ERROR = 1011
    SERVICE_RESTART = 1012
    TRY_AGAIN_LATER = 1013

    def __init__(self, conn, mode='s'):
        # 接受一个socket对象
        self.event_listener_onmessage = []
        self.event_listener_onclose = []
        self.event_listener_onopen = []
        self.conn = conn
        self._state = 0
        self._tmp_data = b''     # 暂存数据
        self.mode = mode

    def open(self):
        self._handshake()
        mode = self.mode
        if mode == 's':
            # 同步模式
            pass
        elif mode == 'a':
            # 异步模式
            # 异步模式下，handle方法失效
            # 先完成onopen
            for func in self.event_listener_onopen:
                func(self)
            from multiprocessing import Process
            p = Process(target=self._listener)
            p.start()
        return self

    def __enter__(self):
        return self.open()

    def getstate(self):
        # 获取连接状态
        state_map = {0: 'READY',
                     1: 'CONNECTION ESTABLISHED',
                     2: 'HANDSHAKE FINISHED',
                     3: 'FAILED',
                     -1: 'CLOSED',
                     4: 'HTTP REQUEST IS'}
        return self._state, state_map[self._state]

    @property
    def state(self):
        """get connection state"""
        return self._state

    def _handshake(self):
        raw_data = b''
        while True:
            fragment = self.conn.recv(1024)
            raw_data += fragment
            if len(fragment) < 1024:
                break
        data = raw_data.decode('utf-8')
        header, content = data.split('\r\n\r\n', 1)
        method_param, *header = header.split('\r\n')
        options = map(lambda i: i.split(': '), header)
        options_dict = {item[0]: item[1] for item in options}
        try:
            # 解析反向代理服务器转发的真实地址
            self.raddr = (options_dict['X-Real-IP'], options_dict['X-Real-Port'])
        except KeyError:
            self.raddr = self.conn.getpeername()
        date = time.strftime("%m,%d%Y", time.localtime())
        if 'Sec-WebSocket-Key' not in options_dict:
            self.conn.send(
                bytes(HTTP_RESPONSE.format(code=501, msg=STATUS_CODE[501], date=date, length=len(date), content=date),
                      encoding='utf-8'))
            self._state = 4
            self.http_req = (method_param.split(' '), options_dict, content)
            return False
        else:
            self._state = 2
            self._build(options_dict['Sec-WebSocket-Key'])
            return True

    def _build(self, sec_key: str) -> bool:
        # 建立WebSocket连接
        response = UPGRADE_WS.format(sec_key_gen(sec_key))
        self.conn.send(bytes(response, encoding='utf-8'))
        self._state = 1
        return True

    @staticmethod
    def _decode(info):
        if info == b'':
            # 空帧意味着对方意外断开连接
            logging.error("Received an Empty data frame")
            raise EmptyFrame()
        payload_len = info[1] & 127
        fin = 1 if info[0] & 128 == 128 else 0
        opcode = info[0] & 15  # 提取opcode

        # 提取载荷数据
        if payload_len == 126:
            # extend_payload_len = info[2:4]
            mask = info[4:8]
            decoded = info[8:]
        elif payload_len == 127:
            # extend_payload_len = info[2:10]
            mask = info[10:14]
            decoded = info[14:]
        else:
            # extend_payload_len = None
            mask = info[2:6]
            decoded = info[6:]

        bytes_list = bytearray()
        # 收集所有数据
        for i in range(len(decoded)):
            chunk = decoded[i] ^ mask[i % 4]
            bytes_list.append(chunk)
        return fin, opcode, bytes_list

    def _recv(self):
        # 处理切片
        raw_data = b''
        while True:
            section = self.conn.recv(1024)
            raw_data += section
            if len(section) < 1024:
                break
        fin, opcode, fragment = self._decode(raw_data)
        if fin == 0:
            # 数据分片，继续递归接收其它分片
            data, _opcode = self._recv()
            fragment += data
        return fragment, opcode

    def handle(self, func=None, args=(), heartbeat=False, timeout: int=-1, cycle: int=-1):
        """接受一个函数作为参数"""
        # todo:Timeout
        if heartbeat:
            from multiprocessing import Process
            p = Process(target=self.ping, args=(cycle,))
            p.start()
        while True:
            data, opcode = self._recv()
            if opcode == 0x08:
                # 客户端请求断开
                # 解析断开请求
                try:
                    code = struct.unpack('!H', data[0:2])[0]
                    reason = data[2:]
                except (IndexError, struct.error):
                    code = 1005
                    reason = b''
                logger.info("Client ask for closing websocket with {}:{}.{}".format(code, reason, self.raddr))
                self.close()
                return code, reason
            elif opcode == 0x0A:
                # PONG
                logger.info('Pong from {}'.format(self.raddr))
            else:
                if func is not None:
                    func(str(data, encoding='utf-8'), *args)

    def add_event_listener(self, callback: callable, type_: str):
        listener = {
             'onopen': self.event_listener_onopen,
             'onmessage': self.event_listener_onmessage,
             'onclose': self.event_listener_onclose
         }.get(type_, None)
        if listener is not None:
            listener.append(callback)

    def _listener(self):
        while self.state == 1:
            data, opcode = self._recv()
            if opcode == self.FRAME_CLOSE:
                self._state = -1
                try:
                    code = struct.unpack('!H', data[0:2])[0]
                    reason = data[2:]
                except (IndexError, struct.error):
                    code = 1005
                    reason = b''
                logger.info("Client ask for closing websocket with {}:{}.{}".format(code, reason, self.raddr))
                self.close()
                return
            elif opcode == 0x0A:
                # PONG
                logger.info('Pong from {}'.format(self.raddr))
            else:
                for func in self.event_listener_onmessage:
                    func(data)

    def send(self, msg, fin=True, isbytes=False):
        # 发送数据
        opcode = 0x02 if isbytes else 0x01
        fin = 1 if fin else 0
        self._send(fin=fin, opcode=opcode, msg=msg)

    def _send(self, fin, opcode, msg):
        bit_1 = struct.pack('B', fin*(2**7) + opcode)
        data = bit_1
        msg_len = len(msg)
        if msg_len <= 125:
            data += struct.pack('B', msg_len)
        elif msg_len <= (2**16 - 1):
            data += struct.pack('!BH', 126, msg_len)
        elif msg_len <= (2**64 - 1):
            data += struct.pack('!BQ', 127, msg_len)
        else:
            # 分片传输超大内容（应该用不到）
            while True:
                fragment = msg[:(2 ** 64 - 1)]
                msg -= fragment
                if msg > (2 ** 64 - 1):
                    if opcode != 0x00:
                        # 第一个切片声明opcode，剩下的切片opcode全部设为0
                        self._send(fin=0, opcode=opcode, msg=fragment)
                    self._send(fin=0, opcode=0x00, msg=fragment)
                else:
                    self._send(fin=1, opcode=0x00, msg=fragment)
                    break
        data += msg
        try:
            self.conn.send(data)
        except BrokenPipeError:
            self._state = -1
            logger.info('Socket connection closed before the last sending.')
        except ConnectionAbortedError:
            self._state = -1
            # raise ForcedClosure('Websocket closed by target.')

    def send_str(self, msg, encoding='utf-8'):
        msg = bytes(msg, encoding=encoding)
        self.send(msg)

    def ping(self, cycle=5):
        ping_msg = 0b10001001
        data = struct.pack('B', ping_msg)
        data += struct.pack('B', 0)
        while self.state == 1:
            self.conn.send(data)
            logger.info('ping {}'.format(self.raddr))
            time.sleep(cycle)

    def sending_coroutine(self):
        """构建一个协程，方便其他模块直接向前传输数据"""
        while True:
            data = yield
            self.send(bytes(data, encoding='utf-8'))

    def close(self, code=1000, reason=b'Normally closed.'):
        self._state = -1
        # 执行关闭事件
        if self.event_listener_onclose:
            for event in self.event_listener_onclose:
                event()
        # 发送关闭控制帧, 关闭码和原因信息
        if self.state:
            code = struct.pack('!H', code)
            msg = code + reason
            self._send(fin=1, opcode=0x08, msg=msg)
        """
        Socket的close方法并不能立即释放连接
        Websocket要求收到关闭帧的一方在返回关闭帧后立即释放连接，否则认为非正常关闭， 状态码1006
        只有在使用multiprocess时会出现这种问题
        socket的shutdown方法的参数
        0:关闭接收通道 SHUT_RD
        1:关闭发送通道 SHUT_WR
        2:两个都关闭
        """
        try:
            self.conn.shutdown(2)      # 两个都关闭
        except OSError:
            logging.info('Connection has been closed by Client {}.'.format(self.raddr))
        self.conn.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is IOError:
            logging.info(exc_val)
            self.close()
            return True
        elif exc_type is WebSocketError:
            logging.info(exc_val)
            self.close()
            return True
        elif exc_type is EmptyFrame:
            logging.info("Client {} closed connection unexpectedly.".format(self.raddr))
            self.close()
            return True
        elif exc_type is ForcedClosure:
            logger.info("Connection {} forced closure.".format(self.raddr))
            self.close()
            return True
        if self.state != -1:
            self.close()
