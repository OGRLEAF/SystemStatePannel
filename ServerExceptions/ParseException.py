# coding=utf-8

class ParamError(Exception):
    def __init__(self, msg):
        """参数错误"""
        self.msg = msg

    @property
    def dict(self):
        reply = {
            'code': 400,
            'msg': self.msg,
            'type': 'ParamError'
            }
        return reply
