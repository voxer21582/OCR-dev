"""Optional synthetic-test sitecustomize hook; logs counts and PIDs, not endpoints.

Copy only into an instrumented *test copy* of the embedded runtime and provide
OCR2_BENCHMARK_NET_LOG. It does not observe native networking or every API.
"""
import os
import socket

_LOG = os.environ['OCR2_BENCHMARK_NET_LOG']
_LOCAL = ('127.0.0.1', '::1', 'localhost', None)


def _write(kind):
    with open(_LOG, 'a', encoding='ascii') as stream:
        stream.write(kind + ' ' + str(os.getpid()) + '\n')


def _remote(address):
    return isinstance(address, tuple) and address[0] not in _LOCAL


_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex
_sendto = socket.socket.sendto
_dns = socket.getaddrinfo


def connect(self, address, *args, **kwargs):
    if _remote(address):
        _write('connect')
    return _connect(self, address, *args, **kwargs)


def connect_ex(self, address, *args, **kwargs):
    if _remote(address):
        _write('connect_ex')
    return _connect_ex(self, address, *args, **kwargs)


def sendto(self, data, *args, **kwargs):
    if args and _remote(args[-1]):
        _write('sendto')
    return _sendto(self, data, *args, **kwargs)


def getaddrinfo(host, *args, **kwargs):
    if host not in _LOCAL:
        _write('dns')
    return _dns(host, *args, **kwargs)


socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
socket.socket.sendto = sendto
socket.getaddrinfo = getaddrinfo
_write('ready')
