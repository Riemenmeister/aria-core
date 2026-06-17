import argparse
import logging
import os
import signal
import socket
import ssl
import threading
from concurrent.futures import ThreadPoolExecutor, wait

from aria_events import EventType, AriaEvent, publish
from aria_voice_notifier import initialize_notifier, VoiceProfile

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 65432
DEFAULT_LOG_FILE = 'aria_listener.log'
DEFAULT_MAX_CLIENTS = 10

shutdown_event = threading.Event()
client_futures = set()
client_futures_lock = threading.Lock()

logger = logging.getLogger('aria_listener')
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

file_handler = None


def configure_logging(log_file):
    global file_handler
    if file_handler:
        logger.removeHandler(file_handler)
        file_handler.close()

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)


def handle_shutdown(signum, frame):
    logger.info('Shutdown requested, closing listener...')
    shutdown_event.set()


def handle_client(conn, addr):
    with conn:
        logger.info('Live-Kopplung mit Gerät hergestellt: %s', addr)
        publish(AriaEvent(event_type=EventType.CLIENT_CONNECTED, payload={'addr': addr, 'message': 'Uplink etabliert.'}))
        conn.settimeout(1.0)
        while not shutdown_event.is_set():
            try:
                data = conn.recv(1024)
            except socket.timeout:
                continue
            except OSError as exc:
                logger.exception('Fehler beim Lesen von Daten: %s', exc)
                publish(AriaEvent(event_type=EventType.STREAM_ERROR, payload={'addr': addr, 'message': 'Achtung. Störung im Datenstrom.'}))
                break

            if not data:
                logger.info('Verbindung vom Client getrennt: %s', addr)
                publish(AriaEvent(event_type=EventType.CLIENT_DISCONNECTED, payload={'addr': addr, 'message': 'Verbindung getrennt.'}))
                break

            try:
                message = data.decode('utf-8', errors='replace')
                logger.info('Live-Sensor-Stream [%s]: %s', addr, message)
            except Exception as decode_error:
                logger.exception('Fehler beim Dekodieren von Daten: %s', decode_error)
                publish(AriaEvent(event_type=EventType.STREAM_ERROR, payload={'addr': addr, 'message': 'Achtung. Dekodierungsfehler im Datenstrom.'}))
                break

    logger.info('Client-Handler beendet: %s', addr)


def cleanup_futures():
    with client_futures_lock:
        done = {future for future in client_futures if future.done()}
        client_futures.difference_update(done)


def run_server(host, port, max_clients, ssl_context=None):
    logger.info('=========================================')
    logger.info(' Guts&Gigaflopps - Aria Live-Core Aktiv ')
    logger.info('=========================================')
    logger.info(f'Lausche auf Port {port}... Warte auf Werkbank-Kopplung.')

    try:
        with ThreadPoolExecutor(max_workers=max_clients) as executor:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

                try:
                    server_socket.bind((host, port))
                except OSError as bind_error:
                    logger.exception('Fehler beim Binden an %s:%d: %s', host, port, bind_error)
                    publish(AriaEvent(event_type=EventType.CRITICAL_ERROR, payload={'message': 'Kritischer Fehler. Port bereits in Verwendung.'}))
                    raise

                server_socket.listen()
                server_socket.settimeout(1.0)
                publish(AriaEvent(event_type=EventType.CORE_STARTED, payload={'message': 'Aria Core online. Horche auf Netzwerk-Port.'}))

                while not shutdown_event.is_set():
                    try:
                        conn, addr = server_socket.accept()
                    except socket.timeout:
                        cleanup_futures()
                        continue
                    except OSError as exc:
                        if shutdown_event.is_set():
                            break
                        logger.exception('Socket error while accepting connection: %s', exc)
                        publish(AriaEvent(event_type=EventType.STREAM_ERROR, payload={'message': 'Fehler beim Akzeptieren der Verbindung.'}))
                        break

                    cleanup_futures()
                    with client_futures_lock:
                        active_clients = len(client_futures)

                    if active_clients >= max_clients:
                        logger.warning('Maximale Client-Anzahl erreicht (%d), neue Verbindung wird verworfen: %s', max_clients, addr)
                        publish(AriaEvent(event_type=EventType.STREAM_ERROR, payload={'message': 'Maximum Clients erreicht.'}))
                        conn.close()
                        continue

                    # If TLS is enabled, wrap the accepted socket before handing off
                    if ssl_context is not None:
                        try:
                            conn = ssl_context.wrap_socket(conn, server_side=True)
                        except Exception as exc:
                            logger.exception('Fehler beim TLS-Handshake mit %s: %s', addr, exc)
                            publish(AriaEvent(event_type=EventType.STREAM_ERROR, payload={'message': 'Fehler beim Sicherheits-Handshake.'}))
                            try:
                                conn.close()
                            except Exception:
                                pass
                            continue

                    future = executor.submit(handle_client, conn, addr)
                    with client_futures_lock:
                        client_futures.add(future)

            logger.info('Warte auf aktive Client-Verbindungen...')
            cleanup_futures()
            with client_futures_lock:
                if client_futures:
                    wait(client_futures, timeout=5.0)

            logger.info('Server wurde sauber beendet.')
        publish(AriaEvent(event_type=EventType.CORE_STARTED, payload={'message': 'Aria Core beendet.'}))

    except Exception as system_error:
        logger.exception('Kritischer Systemfehler: %s', system_error)
        publish(AriaEvent(event_type=EventType.CRITICAL_ERROR, payload={'message': 'Kritischer Systemfehler. Überprüfe das Terminal.'}))
        raise


def parse_args(args=None):
    parser = argparse.ArgumentParser(description='Aria Live-Core TCP Listener')
    parser.add_argument('--host', default=os.environ.get('ARIA_HOST', DEFAULT_HOST), help='Host or interface to bind to')
    parser.add_argument('--port', type=int, default=int(os.environ.get('ARIA_PORT', DEFAULT_PORT)), help='Port to listen on')
    parser.add_argument('--max-clients', type=int, default=int(os.environ.get('ARIA_MAX_CLIENTS', DEFAULT_MAX_CLIENTS)), help='Maximum number of concurrent clients')
    parser.add_argument('--log-file', default=os.environ.get('ARIA_LOG_FILE', DEFAULT_LOG_FILE), help='Path to the log file')
    parser.add_argument('--tls-cert', dest='tls_cert', default=os.environ.get('ARIA_TLS_CERT'), help='Path to TLS certificate (PEM). Enables TLS when both cert and key provided')
    parser.add_argument('--tls-key', dest='tls_key', default=os.environ.get('ARIA_TLS_KEY'), help='Path to TLS private key (PEM).')
    return parser.parse_args(args)


if __name__ == '__main__':
    args = parse_args()
    configure_logging(args.log_file)
    signal.signal(signal.SIGINT, handle_shutdown)
    
    # Initialize Voice Notifier with default profiles
    initialize_notifier(enabled=True)
    
    # Validate TLS configuration: either both cert and key, or none
    ssl_ctx = None
    if (args.tls_cert and not args.tls_key) or (args.tls_key and not args.tls_cert):
        logger.error('TLS configuration invalid: both --tls-cert and --tls-key must be provided together (or neither).')
        publish(AriaEvent(event_type=EventType.CRITICAL_ERROR, payload={'message': 'Fehler in der TLS-Konfiguration.'}))
        raise SystemExit(2)

    if args.tls_cert and args.tls_key:
        try:
            ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_ctx.load_cert_chain(certfile=args.tls_cert, keyfile=args.tls_key)
            logger.info('TLS aktiviert mit Zertifikat: %s', args.tls_cert)
            publish(AriaEvent(event_type=EventType.CORE_STARTED, payload={'message': 'TLS-Sicherheit aktiviert.'}))
        except Exception:
            logger.exception('Fehler beim Laden des TLS-Zertifikats/Schlüssels.')
            publish(AriaEvent(event_type=EventType.CRITICAL_ERROR, payload={'message': 'Fehler beim Laden des TLS-Zertifikats.'}))
            raise

    try:
        run_server(args.host, args.port, args.max_clients, ssl_context=ssl_ctx)
    except Exception:
        logger.exception('Unbehandelter Fehler im Server.')
        publish(AriaEvent(event_type=EventType.CRITICAL_ERROR, payload={'message': 'Kritischer Systemfehler. Überprüfe das Terminal.'}))
    finally:
        shutdown_event.set()
        logger.info('Aria Live-Core gestoppt.')
        publish(AriaEvent(event_type=EventType.CORE_STARTED, payload={'message': 'Aria wird heruntergefahren.'}))
