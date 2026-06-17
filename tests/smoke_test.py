import os
import socket
import sys
import threading
import time
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import aria_listener

TEST_MESSAGE = 'Smoke test message - OK'


def find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    addr, port = s.getsockname()
    s.close()
    return port


def run_smoke_test():
    port = find_free_port()
    log_path = os.path.join(os.path.dirname(__file__), 'test_aria_listener.log')

    # ensure clean log
    try:
        os.remove(log_path)
    except OSError:
        pass

    # configure listener
    aria_listener.shutdown_event.clear()
    aria_listener.configure_logging(log_path)

    server_thread = threading.Thread(target=aria_listener.run_server, args=('127.0.0.1', port, 2), daemon=True)
    server_thread.start()

    # wait for server to start
    time.sleep(1.0)

    # send test message
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=5) as sock:
            sock.sendall((TEST_MESSAGE + "\n").encode('utf-8'))
            sent = True
    except Exception as exc:
        print('client failed:', exc)
        sent = False

    # allow server to process
    time.sleep(1.0)

    # shutdown
    aria_listener.shutdown_event.set()
    server_thread.join(timeout=5.0)

    # read log and verify
    found = False
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()
            found = TEST_MESSAGE in content
    except Exception as exc:
        print('log read failed:', exc)

    print('sent:', sent)
    print('found_in_log:', found)

    if not sent or not found:
        raise SystemExit(2)


if __name__ == '__main__':
    run_smoke_test()
