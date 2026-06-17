aria_listener.py
=================

Simple, configurable TCP listener intended for local Aria Live-Core usage.

Release Description
-------------------

`aria-core` is the foundational software platform for Aria's local bridge between workshop hardware and digital workflows. This release captures the first stable runtime for the listener, voice feedback, and CI-hardened test flow.

Key capabilities:
- Local TCP listener on port `65432` for low-latency data exchange.
- Event-driven core architecture using an `EventBus` to decouple audio, logging, and future extensions.
- Voice feedback through `pyttsx3` and local audio output, including profile-based status and error announcements.
- Stable smoke-test behavior with voice disabled during CI runs.
- A secure software baseline stored in GitHub and tagged for reliable versioning.

Features
- Binds to a configurable host/port and accepts concurrent clients (bounded).
- Structured logging to console and a log file.
- Graceful shutdown on SIGINT (Ctrl+C).
- Configurable via environment variables or CLI arguments.

Configuration
- Environment variables:
  - `ARIA_HOST` - host/interface to bind (default: `0.0.0.0`)
  - `ARIA_PORT` - port to listen on (default: `65432`)
  - `ARIA_MAX_CLIENTS` - maximum concurrent clients (default: `10`)
  - `ARIA_LOG_FILE` - log file path (default: `aria_listener.log`)

  TLS
  ---

  TLS is disabled by default and the server runs in plaintext unless both certificate and private key are provided. You can configure TLS via environment variables or CLI arguments:

  - `ARIA_TLS_CERT` / `--tls-cert` : path to the PEM certificate file
  - `ARIA_TLS_KEY`  / `--tls-key`  : path to the PEM private key file

  The server will refuse to start if only one of the two is provided. When both are set the listener will accept TLS connections only.

CLI arguments (override env vars):
- `--host`
- `--port`
- `--max-clients`
- `--log-file`
- `--tls-cert` (optional)
- `--tls-key` (optional)

Quick examples

Run with defaults:

```powershell
python aria_listener.py
```

Run with environment variables (PowerShell):

```powershell
$env:ARIA_PORT = '22222'
$env:ARIA_MAX_CLIENTS = '4'
python aria_listener.py
```

Run with CLI overrides:

```powershell
python aria_listener.py --host 127.0.0.1 --port 22222 --max-clients 4 --log-file logs/aria.log
```

Smoke test (from workspace root):

```powershell
# start listener in one shell
python aria_listener.py --port 22222

# then in another shell
$client = New-Object System.Net.Sockets.TcpClient('127.0.0.1', 22222)
$stream = $client.GetStream()
$writer = New-Object System.IO.StreamWriter($stream)
$writer.AutoFlush = $true
$writer.WriteLine('Hello from test client')
$client.Close()
```

Implemented capabilities
- Simple smoke test script under `tests/`.
- Docker Compose support for local container runs.
- Optional TLS support with self-signed certificate helpers.
- Windows service helper integration via NSSM.

Windows Service (NSSM)
----------------------

For Windows, the simplest reliable service wrapper is NSSM (Non-Sucking Service Manager). Below are instructions and a helper script that prints the NSSM commands it will run and can optionally install/uninstall the service.

Prerequisites:
- Download and extract NSSM (https://nssm.cc/) and ensure `nssm.exe` is on your PATH or located at `C:\nssm\win64\nssm.exe`.
- Have Python installed and accessible.

Helper script: `windows/install_service.ps1`

Examples (PowerShell):

```powershell
# Preview commands (no install)
.\windows\install_service.ps1 -ServiceName AriaListener -PythonPath "C:\Python311\python.exe" -ScriptPath "C:\AriaCore\aria_listener.py" -ListenHost 0.0.0.0 -Port 65432 -LogFile "C:\AriaCore\logs\aria.log"

# Install the service (runs NSSM commands)
.\windows\install_service.ps1 -ServiceName AriaListener -PythonPath "C:\Python311\python.exe" -ScriptPath "C:\AriaCore\aria_listener.py" -LogFile "C:\AriaCore\logs\aria.log" -Install

# Uninstall the service
.\windows\install_service.ps1 -ServiceName AriaListener -Uninstall
```

Notes:
- TLS and log-file paths are supported as script parameters and will be included in the service parameters when installing via NSSM.
- The helper prints the NSSM commands before executing them so you can review and run them manually if preferred.

Notes
- `aria_listener.py` uses only Python standard library modules.
- The listener writes logs to both console and the configured log file.

Aria Knowledge Bridge
---------------------

`aria_knowledge.py` connects Aria to Wikipedia and stores mentor observations from
Gemini or other sources in a local JSONL memory file.

Wikipedia summaries use the public Wikipedia REST API. No API key is required:

```powershell
py aria_knowledge.py wiki "Kuenstliche Intelligenz" --lang de
```

Search Wikipedia:

```powershell
py aria_knowledge.py search "TCP Server" --lang de --limit 3
```

Store a Gemini mentor observation:

```powershell
py aria_knowledge.py learn "Gemini empfiehlt: Aussagen mit mehreren Quellen vergleichen." --source gemini
```

Review recent mentor observations:

```powershell
py aria_knowledge.py memory --limit 5
```

Configuration:
- `ARIA_WIKI_LANG` - default Wikipedia language code (default: `de`)
- `ARIA_WIKI_USER_AGENT` - custom Wikipedia User-Agent string
- `ARIA_MENTOR_MEMORY` - mentor memory JSONL path (default: `memory/gemini_mentor.jsonl`)

The local `memory/` folder is ignored by Git so mentor notes stay local by default.

Docker
------

Build the Docker image (from workspace root):

```bash
docker build -t aria_listener:local .
```

Run the container and publish the listener port:

```bash
docker run --rm -p 65432:65432 --name aria_test aria_listener:local
```

If you want logs available on the host, map a host directory and override `ARIA_LOG_FILE`:

```bash
mkdir -p logs
docker run --rm -p 65432:65432 -v ${PWD}/logs:/var/log -e ARIA_LOG_FILE=/var/log/aria_listener.log --name aria_test aria_listener:local
```

Then use `docker logs aria_test` or inspect `logs/aria_listener.log` on the host.

Docker Compose
--------------

A lightweight `docker-compose.yml` is provided to help verify the container locally.

- Service `aria-listener` builds from the local `Dockerfile` and maps `65432:65432`.
- Logs are mapped from `./logs` on the host to `/var/log` in the container by default.
- An optional short-lived `smoke-test` service connects to the listener and sends a single message.

Run the compose setup (build + start):

```bash
docker compose up --build
```

Run only the listener:

```bash
docker compose up --build aria-listener
```

Run the smoke-test alongside the listener:

```bash
docker compose up --build aria-listener smoke-test
```

If you mounted `./logs` as shown in the Dockerfile, inspect `./logs/aria_listener.log` on the host after the test.

Mounting certificates for TLS in Compose
--------------------------------------

To enable TLS when running with Docker Compose, place your `server.crt` and `server.key` under `./certs` and run:

```bash
docker compose up --build aria-listener
```

The provided `docker-compose.yml` mounts `./certs` into the container at `/certs` and sets example env vars `ARIA_TLS_CERT=/certs/server.crt` and `ARIA_TLS_KEY=/certs/server.key`.

Generate local self-signed certs (dev only)
-----------------------------------------

For local development you can quickly generate a self-signed certificate pair. These are only suitable for testing — do not use in production.

Bash (requires `openssl`):

```bash
./certs/generate_certs.sh
```

PowerShell (Windows, requires `openssl` on PATH):

```powershell
.\certs\generate_certs.ps1
```

The scripts create `certs/aria.crt` and `certs/aria.key`. The repository `.gitignore` is configured to avoid committing these files.

To use them with Docker Compose (the compose file expects `aria.crt`/`aria.key`):

```bash
docker compose up --build aria-listener
```

If you prefer the files named `server.crt`/`server.key`, copy or rename them inside `./certs` accordingly.

## v0.2.1 - Voice Feedback Stabilization

### Added
- Added voice profiles for info, warning, critical, and success messages.
- Added `force=True` support for critical real-time audio alerts.

### Fixed
- Moved startup voice output until after the TCP socket is listening.
- Disabled voice output in automated smoke tests to avoid TTS timing issues.
- Prevented repeated identical events from spamming audio output through cooldowns.

### Verified
- CI passed before tagging.
- Local listener startup, repeated disconnects, and critical bind-error paths were tested.

