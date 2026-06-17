import os
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import shutil

from pathlib import Path

TEST_MESSAGE = 'TLS smoke test message — ✓'


def find_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    addr, port = s.getsockname()
    s.close()
    return port


def generate_self_signed_cert(cert_path: Path, key_path: Path):
    # Use openssl to generate a self-signed cert; require openssl available on PATH
    if shutil.which('openssl') is None:
        return False

    cmd = [
        'openssl', 'req', '-x509', '-nodes', '-newkey', 'rsa:2048', '-days', '1',
        '-keyout', str(key_path), '-out', str(cert_path), '-subj', '/CN=localhost'
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise RuntimeError(f'OpenSSL failed: {res.stderr.decode().strip()}')
    return True


def run_tls_smoke_test():
    tmpdir = Path(tempfile.mkdtemp(prefix='aria-tls-test-'))
    cert_path = tmpdir / 'server.crt'
    key_path = tmpdir / 'server.key'
    log_path = tmpdir / 'tls_test.log'

    try:
        ok = generate_self_signed_cert(cert_path, key_path)
    except Exception as exc:
        print('SKIP: could not generate cert (openssl failed):', exc)
        return

    if not ok:
        print('SKIP: openssl not found; skipping TLS smoke test')
        return

    port = find_free_port()

    # Start aria_listener as a subprocess with TLS args
    proc = subprocess.Popen([
        sys.executable, 'aria_listener.py',
        '--host', '127.0.0.1',
        '--port', str(port),
        '--tls-cert', str(cert_path),
        '--tls-key', str(key_path),
        '--log-file', str(log_path)
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        # Wait briefly for server to start
        time.sleep(1.5)

        # Create an unverified client SSL context (for self-signed cert)
        client_ctx = ssl.create_default_context()
        client_ctx.check_hostname = False
        client_ctx.verify_mode = ssl.CERT_NONE

        with socket.create_connection(('127.0.0.1', port), timeout=5) as sock:
            with client_ctx.wrap_socket(sock, server_hostname=None) as ssock:
                ssock.sendall((TEST_MESSAGE + "\n").encode('utf-8'))

        # Allow server to process
        time.sleep(1.0)

        # Request graceful shutdown
        proc.send_signal(subprocess.signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

        # Verify message in log
        found = False
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()
            found = TEST_MESSAGE in content

        print('found_in_log:', found)
        if not found:
            raise SystemExit(2)

    finally:
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass
        # cleanup
        try:
            for p in [cert_path, key_path, log_path]:
                if p.exists():
                    p.unlink()
            tmpdir.rmdir()
        except Exception:
            pass


if __name__ == '__main__':
    run_tls_smoke_test()
