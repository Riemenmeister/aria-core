# AEGIS Split-Brain Architecture

This note captures the current safety and architecture decision for the AEGIS drone concept in Aria Core.

## Decision

A DVB receiver, such as a GTMedia receiver, must not be used as the flight brain for a drone.

A safe AEGIS design uses a split-brain architecture:

- Motor brain: a dedicated flight controller, such as Pixhawk, Matek, or a comparable drone flight controller.
- Cognitive brain: Aria Core running on a laptop, mini PC, or companion computer for planning, monitoring, knowledge, security scans, and higher-level mission logic.
- Ground-station media role: a GTMedia receiver can only be considered as an external decoder or ground-station component, not as airborne flight-control hardware.

## Why the receiver cannot replace a flight controller

A DVB receiver is built to decode video or broadcast signals. It lacks the core real-time hardware required to keep a drone stable:

- IMU sensors: gyroscopes and accelerometers for millisecond-level attitude detection.
- Motor I/O: PWM, DShot, or equivalent outputs for ESC control.
- Real-time control loop: deterministic flight stabilization timing.
- Flight safety model: arming, failsafe, radio/telemetry integration, and power-distribution assumptions.

## USB safety warning

Do not connect a laptop and DVB receiver using a host-to-host USB cable such as USB-A to USB-A unless the hardware explicitly supports a safe device/client mode.

Both devices are normally USB hosts and may both provide power. Connecting host to host can damage USB controllers or cause a short.

## Recommended AEGIS integration model

```text
Aria Core / Laptop
  - Knowledge Bridge
  - EventBus
  - Voice feedback
  - Safety and scan routines
  - Mission planning
          |
          | telemetry / Wi-Fi / serial bridge
          v
Flight Controller
  - IMU fusion
  - stabilization loop
  - ESC/motor outputs
  - failsafe behavior
          |
          v
Drone frame, ESCs, motors, battery, radio link
```

Aria should send high-level intent only, such as mission state, coordinates, hold/return commands, or safe-mode requests. Low-level stabilization remains inside the flight controller.

## Next implementation direction

Future Aria work should model AEGIS as events, not direct motor control:

- `AEGIS_SAFETY_WARNING`
- `AEGIS_MISSION_NOTE`
- `AEGIS_TELEMETRY_UPDATE`
- `AEGIS_LINK_STATUS`

These can later feed voice output, logs, dashboards, or companion-computer integrations without coupling Aria Core to unsafe hardware assumptions.
