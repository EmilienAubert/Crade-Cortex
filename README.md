# Crade Cortex

**English** · [Français](README.fr.md)

A DIY MIDI footswitch controller for [PiPedal](https://github.com/rerdavies/pipedal)
with **closed-loop state feedback**: the LEDs and display don't show what your
foot asked for, they show what the Raspberry Pi confirmed.

A Pico running CircuitPython sends MIDI. A Python daemon on the Pi subscribes to
PiPedal's websocket and pushes state back over the same USB cable. One state
exists — PiPedal's — and the whole class of desynchronisation bugs disappears by
construction.

This repository also contains
[documentation of PiPedal's undocumented internal websocket protocol](docs/PROTOCOL.md),
reverse-engineered from version 2.0.110. That is probably the most reusable part
of it for other projects.

---

## What it does

- **4 snapshots** with exclusive selection, confirmed by the Pi
- **Preset changes** with the LED held lit through the NAM model load
- **Tuner** on the display — note and cents, subscribed only on demand
- **16×2 LCD** — pedalboard and snapshot names, boot animation
- **Dead-link detection** — blinking LEDs and an on-screen marker

```
              MIDI CC 102-113 (USB MIDI -> ALSA)
        ┌──────────────────────────────────────────────┐
        │                                              ▼
   ┌─────────┐          ┌──────────────────┐      ┌──────────┐
   │  Pedal  │◄────────►│ pipedal_bridge.py│◄─────│ pipedald │
   │  Pico   │  serial  │     (daemon)     │  ws  │ (PiPedal)│
   └─────────┘          └──────────────────┘      └──────────┘
    S3  N:  T:              A1  A0  ?
```

MIDI does **not** go through the daemon: the Pico talks straight to `pipedald`
via ALSA. The daemon only handles the return path.

---

## Hardware

| Item | Detail |
|---|---|
| Controller | Raspberry Pi Pico (RP2040), CircuitPython |
| Host | Raspberry Pi, PiPedal 2.0.110 |
| Display | LCD1602, HD44780, 4-bit mode |
| Switches | 8 SPST momentary footswitches |
| LEDs | 8, PWM at 2 kHz, one resistor each |

Full wiring, pinout and assembly order: **[docs/WIRING.md](docs/WIRING.md)**

---

## Installation

### On the Pico

#### 1. Install CircuitPython

Download the `.uf2` for the Raspberry Pi Pico from
[circuitpython.org](https://circuitpython.org/board/raspberry_pi_pico/).

Hold **BOOTSEL** down **before** plugging in the USB cable, then release it. An
`RPI-RP2` drive appears. Drop the `.uf2` onto it: the Pico reboots on its own and
a `CIRCUITPY` drive takes its place.

If the Pico was running different firmware, or if the major version changes, the
install can leave an inconsistent filesystem. In that case run
[`flash_nuke.uf2`](https://learn.adafruit.com/circuitpython-with-raspberry-pi-pico/resetting-flash)
first to wipe the flash completely.

#### 2. Install the libraries

Download the [CircuitPython bundle](https://circuitpython.org/libraries) —
**the one matching your installed major version**. A 9.x bundle on 10.x firmware
produces import errors that are hard to diagnose. The version is written in
`boot_out.txt` at the root of `CIRCUITPY`.

Copy these two folders into `/lib`:

```
lib/
  adafruit_midi/              USB MIDI
  adafruit_character_lcd/     HD44780 driver
```

Whole folders, not just the `.py` files you think you need.

#### 3. Copy the project

To the root of `CIRCUITPY`:

```
boot.py  code.py  ecran.py  retour_pipedal.py
```

On Linux, run `sync` before unplugging. The `CIRCUITPY` filesystem is small and
corrupts easily if a write hasn't finished.

#### 4. Restart

`boot.py` is only re-read on a **hard reset**: unplug and plug back in. Saving
the file is not enough — that's the classic trap.

Saving `code.py`, on the other hand, restarts the program automatically.

#### Checking

`boot_out.txt` holds the CircuitPython version and, when something goes wrong,
the reason it dropped into safe mode. It's the first place to look if the display
stays dark or nothing starts.

```bash
ls /dev/ttyACM*        # two ports should appear: console and data
```

### On the Raspberry Pi

```bash
sudo apt install python3-serial
pip3 install websockets --break-system-packages
```

A udev rule for a stable port name — without it, the `ttyACM` number changes with
plug order:

```
# /etc/udev/rules.d/99-pipedal-pico.rules
SUBSYSTEM=="tty", ATTRS{idVendor}=="239a", ATTRS{product}=="Pedalier", \
  ENV{ID_USB_INTERFACE_NUM}=="02", SYMLINK+="pipedal-pico"
```

```bash
sudo udevadm control --reload && sudo udevadm trigger
python3 pi/pipedal_bridge.py -v
```

A sample systemd unit is provided in `pi/pipedal-bridge.service`.

### MIDI bindings in PiPedal

| System symbol | CC |
|---|---|
| `snapshot1` … `snapshot4` | 102 … 105 |
| `prevProgram` | 110 |
| `nextProgram` | 111 |

CC 112 drives the tuner locally. Binding it to the TooB Tuner's `MUTE` control
lets one press both mute the signal and bring up the tuner.

---

## Documentation

| Document | Contents |
|---|---|
| [docs/PROTOCOL.md](docs/PROTOCOL.md) | **PiPedal's websocket protocol**, reverse-engineered |
| [docs/WIRING.md](docs/WIRING.md) | Pinout, wiring, assembly order, checks |
| [docs/index.html](docs/index.html) | Full documentation, laid out |

---

## The principle

> PiPedal is the single source of truth. The Pico holds no state of its own.

Pressing a switch sends a CC, nothing more. The LED only lights when the Pi's
confirmation arrives. That's what keeps the display honest whatever caused the
change — your foot, the phone, or a `pipedald` restart.

Two safeguards cover link failure, because a closed loop that opens would leave
the LEDs frozen on the last value received:

- **Optimistic fallback at 200 ms** — with no confirmation, the LED lights
  anyway. Degraded, but playable.
- **Heartbeat at 1 Hz** — three missed beats and the active LED blinks, with a
  `!` on the display.

---

## Serial protocol

One ASCII line per event, bidirectional.

| Direction | Frame | Meaning |
|---|---|---|
| Pi → Pico | `S<n>` | Active snapshot, 1-based |
| | `HB` | Heartbeat |
| | `N:<text>` | Pedalboard name |
| | `M:<text>` | Snapshot name |
| | `T:<note>:<cents>` | Tuner |
| Pico → Pi | `A1` / `A0` | Enter / leave tuner mode |
| | `?` | Request full state |

The `?` beacon deserves an explanation: the daemon caches state and only emits on
change. When the Pico restarts, nothing has changed on PiPedal's side — without
this explicit request the pedal would stay blind until the next real change.

---

## Tools

`outils/banc_test_led.py` — a test bench to copy onto a second Pico. Three
looping phases: all LEDs at real brightness so you can match channels, a chase to
identify positions, and full brightness to spot a dead or reversed LED.

Rename it to `code.py` on the test Pico.

---

## A warning about the websocket protocol

PiPedal's websocket API is **internal and undocumented**. This repository
publishes a description captured from version **2.0.110**. It will change between
versions, without notice, and that won't be a bug on PiPedal's side.

If you build on it, pin yourself to a known version and plan to re-verify after
every update.

---

## Licence

MIT. See [LICENSE](LICENSE).

Developed with assistance from Claude (Anthropic). The architecture, the protocol
reverse-engineering and the engineering trade-offs came out of iterative work
between a human and the model.

Source comments are in French.

---

## Acknowledgements

[Robin Davies](https://github.com/rerdavies) for PiPedal, which runs a serious
effects processor on a Raspberry Pi, and whose architecture — a single
server-side model broadcast to every client — is what makes this kind of project
possible at all.
