#!/usr/bin/env python3
"""Run the actual TorNetwork Swift code against a mock SOCKS proxy and a direct trap.
No request leaves this machine. Checks remote DNS plus failure without direct fallback.
"""
import socket
import subprocess
import sys
import threading

binary = sys.argv[1]
errors = []
direct_hits = []

def read_exact(client, count):
    result = b''
    while len(result) < count:
        part = client.recv(count - len(result))
        if not part:
            raise RuntimeError('SOCKS client closed early')
        result += part
    return result

def proxy(server, redirect=False):
    try:
        client, _ = server.accept()
        with client:
            client.settimeout(15)
            version, nmethods = read_exact(client, 2)
            methods = read_exact(client, nmethods)
            assert version == 5 and 0 in methods, (version, methods)
            client.sendall(b'\x05\x00')
            version, command, reserved, kind = read_exact(client, 4)
            assert version == 5 and command == 1 and kind == 3, 'DNS must be sent as SOCKS hostname'
            host = read_exact(client, read_exact(client, 1)[0]).decode()
            read_exact(client, 2)
            assert host == 'tor-routing-test.invalid', host
            client.sendall(b'\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x50')
            request = b''
            while b'\r\n\r\n' not in request:
                request += client.recv(4096)
            body = b'tor-proxy-sentinel'
            if redirect:
                client.sendall(b'HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1:19051/\r\nConnection: close\r\nContent-Length: 0\r\n\r\n')
            else:
                client.sendall(b'HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body)
    except Exception as error:
        errors.append(str(error))
    finally:
        server.close()

def trap(server):
    server.settimeout(22)
    try:
        client, address = server.accept()
        direct_hits.append(address)
        client.close()
    except socket.timeout:
        pass
    finally:
        server.close()

def listener(port):
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', port))
    server.listen(5)
    return server

trap_thread = threading.Thread(target=trap, args=(listener(19051),), daemon=True)
trap_thread.start()
for prefix in ['', 'download-']:
    thread = threading.Thread(target=proxy, args=(listener(19050),), daemon=True)
    thread.start()
    subprocess.run([binary, prefix + 'routing'], check=True, timeout=25)
    thread.join(timeout=20)
    assert not errors, errors
    assert not thread.is_alive(), 'Proxy test did not terminate'
    # The SOCKS listener is now gone. No direct fallback may reach any origin.
    subprocess.run([binary, prefix + 'failure'], check=True, timeout=25)
    for phase in ['local', 'short-ip', 'octal-ip', 'hex-ip']:
        subprocess.run([binary, prefix + phase], check=True, timeout=25)
    redirect_thread = threading.Thread(target=proxy, args=(listener(19050), True), daemon=True)
    redirect_thread.start()
    subprocess.run([binary, prefix + 'redirect'], check=True, timeout=25)
    redirect_thread.join(timeout=20)
    assert not errors, errors
    assert not direct_hits, 'Native request or redirect bypassed Tor proxy'
print('Data/download remote DNS, no-direct-fallback, local address and redirect checks passed')
