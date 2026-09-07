# PiPedal websocket protocol

**English** · [Français](PROTOCOLE.md)

Captured from **PiPedal 2.0.110**, on the browser side.

> **Internal API, undocumented by the project.** It will change between versions.
> Pin yourself to a known version and re-verify after every update. Nothing below
> is a contract.

**Endpoint:** `ws://<host>:80/pipedal`

Port 80 is the default on Raspberry Pi OS. On Ubuntu, PiPedal usually falls back
to 81 because Apache holds 80. `pipedalconfig` can change it.

---

## Envelope

A JSON array of one or two elements: `[header]` or `[header, body]`.

```jsonc
// request with no argument
[{"message": "hello", "replyTo": 2}]

// request with an argument
[{"message": "monitorPort", "replyTo": 24},
 {"instanceId": 16, "key": "FREQ", "updateRate": 0.05}]

// server response
[{"reply": 2, "message": "ehlo"}, 20]
```

Two fields, never together:

- **`replyTo`** — "answer me with this id". Present on client requests, and on
  server-pushed messages that expect an acknowledgement.
- **`reply`** — "this is the answer to that id".

This is **not** JSON-RPC 2.0. The implementation is a hand-written remote-object
proxy between `PiPedalModel.tsx` on the client and `PiPedalModel.cpp` on the
server.

---

## Handshake

**The client must send `hello` on connect.**

```jsonc
[{"message": "hello", "replyTo": 2}]
[{"reply": 2, "message": "ehlo"}, 20]
```

Without it the server accepts the connection, answers requests, and **never
broadcasts anything**. It's a silent failure: everything looks fine until you
notice no events ever arrive.

---

## Acknowledgements

When a pushed message's header carries `replyTo`, the client must answer:

```jsonc
[{"replyTo": 996, "message": "onVuUpdate"}, { … }]
[{"reply": 996, "message": "onVuUpdate"}, true]
```

This is flow control: the server numbers each message, waits for the ack, and
only then sends the next. A client that doesn't acknowledge eventually stops
receiving anything.

`onPedalboardChanged` has no `replyTo` and expects nothing.

---

## Pedalboard state

### Change broadcast

Sent to **every** connected client, including the one that caused the change.
That's what lets a physical controller confirm its own actions.

```jsonc
[{"message": "onPedalboardChanged"},
 {"clientId": -1,
  "pedalboard": {
    "name": "Fender Clean",
    "selectedSnapshot": 1,        // ZERO-BASED
    "selectedPlugin": 16,
    "items": [
      {"instanceId": 16,
       "uri": "http://two-play.com/plugins/toob-tuner",
       "isEnabled": true,
       "controlValues": [{"key": "MUTE", "value": 0}, …],
       "midiBindings": [ … ]},
      …
    ],
    "snapshots": [
      {"name": "Default", "color": "purple", "isModified": false,
       "values": [ … ]},
      null, null, null, null
    ]
  }}]
```

Things worth knowing:

- **`selectedSnapshot` is zero-based.**
- **`snapshots` contains holes** (`null`) for empty slots. Don't assume the index
  is valid.
- **Each broadcast is around 9 kB**: the entire pedalboard is resent, not just
  what changed. Raise `max_size` on the connection.
- **`isModified`** flags a snapshot that has been edited but not saved.
- **`color`** is the snapshot colour as shown in the UI.

### Initial state

```jsonc
[{"message": "currentPedalboard", "replyTo": 8}]
```

The response puts the pedalboard **at the root of the body**, not under a
`pedalboard` key as the broadcast does:

```jsonc
[{"reply": 8, "message": "currentPedalboard"},
 {"name": "Fender Clean", "selectedSnapshot": 0, "items": [ … ]}]
```

### Command

```jsonc
[{"message": "setSnapshot"}, 0]
```

---

## Port monitoring

Streams the value of an LV2 output port.

```jsonc
[{"message": "monitorPort", "replyTo": 24},
 {"instanceId": 16, "key": "FREQ", "updateRate": 0.05}]

// the response carries the subscription handle
[{"reply": 24, "message": "monitorPort"}, 29]

// then, periodically
[{"replyTo": 2, "message": "onMonitorPortOutput"},
 {"subscriptionHandle": 29, "value": 40.12}]

// unsubscribe
[{"message": "unmonitorPort"}, 29]
```

`updateRate` is a **period in seconds**, not a frequency. The web client uses
0.0333 (30 Hz) and 0.0667 (15 Hz).

### Example: the tuner

The **TooB Tuner** plugin (`http://two-play.com/plugins/toob-tuner`) exposes a
`FREQ` port carrying a **floating-point MIDI note number**, or `-1` when there is
no signal.

```python
NOTES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

def note_and_cents(value):
    if value is None or value < 0:
        return (None, 0)
    n = int(round(value))
    cents = int(round((value - n) * 100))
    return (NOTES[n % 12] + str(n // 12 - 1), cents)
```

**Never hard-code the `instanceId`.** It changes with the pedalboard. Find it in
`items` by matching the plugin URI, and re-subscribe when it moves.

### Other useful output ports

Taken from the `plugins` descriptor:

| Plugin | Output port | Contents |
|---|---|---|
| TooB Neural Amp Modeler | `gateOut` | Noise gate state, 0 or 1 |
| TooB NAM | `inputGainOut` | Input level in dB |
| Gxdigital_delay | `DD_NOTIFY` | Tempo in BPM |
| TooB 4Looper | `position1` | Position within the loop, 0 to 1 |
| TooB 4Looper | `record_led1`, `play_led1` | Record and play state |
| TooB 4Looper | `bar_led`, `beat_led` | Bars and beats |
| TooB File Player | `position`, `duration`, `state` | File playback |

---

## VU meters

```jsonc
[{"message": "addVuSubscription", "replyTo": 23}, 16]
[{"reply": 23, "message": "addVuSubscription"}, 28]

[{"replyTo": 996, "message": "onVuUpdate"},
 {"instanceId": 16, "sampleTime": 2741501184,
  "isStereoInput": false, "isStereoOutput": false,
  "inputMaxValueL": 6.55e-05, "inputMaxValueR": 0,
  "outputMaxValueL": 6.55e-05, "outputMaxValueR": 0}]
```

These messages **require an acknowledgement**. The stream is dense: only
subscribe when you actually need it.

---

## System MIDI bindings

```jsonc
[{"message": "getSystemMidiBindings", "replyTo": 22}]
```

Available symbols:

```
prevBank      nextBank
prevProgram   nextProgram
snapshot1 … snapshot6
prevSnapshot  nextSnapshot
startHotspot  stopHotspot
shutdown      reboot
```

`shutdown` and `reboot` let a footswitch shut the Raspberry Pi down cleanly.
That's not a detail: cutting power without an orderly shutdown can lose presets,
banks and configuration.

Binding structure:

```jsonc
{"channel": -1, "symbol": "snapshot1", "bindingType": 2,
 "note": 72, "control": 102,
 "minControlValue": 0, "maxControlValue": 127,
 "minValue": 0, "maxValue": 1,
 "rotaryScale": 1, "linearControlType": 0, "switchControlType": 0}
```

`bindingType` is 0 when the binding is inactive, 2 for a MIDI CC control.

---

## Other observed messages

| Message | Contents |
|---|---|
| `version` | Server version, OS, web addresses |
| `plugins` | Full descriptor of every LV2 plugin — very large |
| `pluginClasses` | Plugin type taxonomy |
| `getPresets` | Preset list with `instanceId` and name |
| `getBankIndex` | Available banks and current selection |
| `getJackConfiguration` | Sample rate, buffer size, audio and MIDI ports |
| `getJackServerSettings` | ALSA device, buffers |
| `getUpdateStatus` | Update availability |
| `getShowStatusMonitor` | System monitor display setting |
| `imageList` | UI graphic assets |
| `getFavorites`, `getWifiConfigSettings`, `getGovernorSettings` | Configuration |

---

## Web client startup sequence

For reference, the order observed when the page loads:

```
getWifiRegulatoryDomains → hello → imageList → version → getUpdateStatus
→ getHasWifi → plugins → currentPedalboard → pluginClasses → getPresets
→ getWifiConfigSettings → … → getSystemMidiBindings
→ addVuSubscription → monitorPort ×4
```

A minimal client only needs `hello` then `currentPedalboard`.

---

## Reference implementation

`pi/pipedal_bridge.py` in this repository: around 400 lines, with reconnection,
acknowledgements, conditional subscription and rate limiting. Comments are in
French.
