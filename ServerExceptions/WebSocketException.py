# coding=utf-8

class WebSocketError(Exception):
    def __init__(self, msg):
        """websocket连接失败"""
        self.msg = msg

class EmptyFrame(Exception):
    """空信息帧，说明对方意外断开连接"""

class CloseFrame(Exception):
    """用于断开连接，跳出with"""

class ForcedClosure(Exception):
    """对方直接关闭socket"""
