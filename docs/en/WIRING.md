# Crade Cortex — wiring

**English** · [Français](../fr/CABLAGE.md)

Derived from `code.py`. Any change to the pin assignment in the code must be
reflected here, and the other way round.

---

## 1. Pico physical pinout

The Pico has 40 pins. Pin 1 is top-left with the USB connector facing up.
Numbering runs down the left side to 20, then back up the right side from 21 to
40.

```
                    ┌───── USB ─────┐
      S1   GP0  ────┤ 1          40 ├──── VBUS  → LCD 2 and 15
      S2   GP1  ────┤ 2          39 │     VSYS
           GND      │ 3          38 ├──── GND   → ground rail
      S3   GP2  ────┤ 4          37 │     3V3_EN
      S4   GP3  ────┤ 5          36 │     3V3 OUT   (do not use)
   Prst-   GP4  ────┤ 6          35 │     ADC_VREF
   Prst+   GP5  ────┤ 7          34 │     GP28
           GND      │ 8          33 │     AGND
   Tuner   GP6  ────┤ 9          32 │     GP27
   Spare   GP7  ────┤ 10         31 │     GP26
    LED1   GP8  ────┤ 11         30 │     RUN
    LED2   GP9  ────┤ 12         29 │     GP22
           GND      │ 13         28 │     GND
  LCD RS   GP10 ────┤ 14         27 ├──── GP21   LED8
  LCD E    GP11 ────┤ 15         26 ├──── GP20   LED7
  LCD D4   GP12 ────┤ 16         25 ├──── GP19   LED6
  LCD D5   GP13 ────┤ 17         24 ├──── GP18   LED5
           GND      │ 18         23 │     GND
  LCD D6   GP14 ────┤ 19         22 ├──── GP17   LED4
  LCD D7   GP15 ────┤ 20         21 ├──── GP16   LED3
                    └───────────────┘
```

**22 pins used out of 26 available.** Free: `GP22`, `GP26`, `GP27`, `GP28`.

> **Never power the LCD from pin 36 (3V3).** It needs 5 V, so pin 40 (VBUS). An
> HD44780 on 3.3 V either stays dark or shows garbage.

---

## 2. Pin map

| GPIO | Physical pin | Function |
|---|---|---|
| `GP0` | 1 | Switch S1 |
| `GP1` | 2 | Switch S2 |
| `GP2` | 4 | Switch S3 |
| `GP3` | 5 | Switch S4 |
| `GP4` | 6 | Switch F1 — previous preset |
| `GP5` | 7 | Switch F2 — next preset |
| `GP6` | 9 | Switch F3 — tuner |
| `GP7` | 10 | Switch F4 — spare |
| `GP8` | 11 | LED 1 |
| `GP9` | 12 | LED 2 |
| `GP10` | 14 | LCD — RS |
| `GP11` | 15 | LCD — E |
| `GP12` | 16 | LCD — D4 |
| `GP13` | 17 | LCD — D5 |
| `GP14` | 19 | LCD — D6 |
| `GP15` | 20 | LCD — D7 |
| `GP16` | 21 | LED 3 |
| `GP17` | 22 | LED 4 |
| `GP18` | 24 | LED 5 |
| `GP19` | 25 | LED 6 |
| `GP20` | 26 | LED 7 |
| `GP21` | 27 | LED 8 |
| — | 38 | GND — ground rail |
| — | 40 | VBUS — 5 V to the LCD |

LEDs 1 and 2 sit on the left side while LEDs 3 to 8 are on the right. That's
inherited from the original `GP8`/`GP9` wiring. Moving them would only tidy the
loom, at the cost of rewiring something that already works.

---

## 3. Front-panel layout

Two rows of four, left to right. The front row is the one you use most, so it
goes closest to the edge.

```
   back    [ Preset - ] [ Preset + ] [   Tuner   ] [ Spare  ]
                GP4          GP5          GP6         GP7
                CC 110       CC 111       CC 112      CC 113

   front   [    S1    ] [    S2    ] [    S3     ] [   S4   ]
                GP0          GP1          GP2         GP3
                CC 102       CC 103       CC 104      CC 105
```

**LEDs go above the switches, never below.** Your foot covers the lower area
during the press: an LED below the switch is only visible once you lift off,
which is too late.

**At least 25 mm between the two rows**, measured centre to centre; 40 mm if
there's room. Below that, your heel catches the back row while pressing the front
one.

### Matching PiPedal bindings

| System symbol | CC |
|---|---|
| `snapshot1` … `snapshot4` | 102 … 105 |
| `prevProgram` | 110 |
| `nextProgram` | 111 |

Optional: bind CC 112 to the TooB Tuner's `MUTE` control so one press both mutes
and brings up the tuner.

---

## 4. The ground rail

Nineteen connections go to ground: eight switches, eight LEDs, three LCD pins.
Soldering them all to pin 38 isn't practical.

**Build a rail.** A bare copper wire, or a track on stripboard, running the length
of the assembly. A single link ties it to pin 38. Each individual ground joins it
at the nearest point.

```
     pin 38 ────┬──────┬──────┬──────┬──────┬──────┬─────
                │      │      │      │      │      │
             LCD 1   LED1   LED2    S1     S2    LED3  …
             LCD 5
             LCD 16
```

**What you want to avoid is daisy-chaining** — LED1 to LED2 to LED3 to the Pico.
Electrically it would work at 50 mA, but one bad joint halfway along takes
everything downstream with it, and you lose an evening finding it.

The rail gives you one identifiable failure point instead of nineteen in series.

---

## 5. The switches

No resistors. The Pico's internal pull-ups are enabled in code
(`digitalio.Pull.UP`), so the switches are active-low.

```
   GPx ────────────○ ○──────────── ground rail
                 switch
```

| Switch | To |
|---|---|
| S1 | pin 1 and ground |
| S2 | pin 2 and ground |
| S3 | pin 4 and ground |
| S4 | pin 5 and ground |
| F1 — preset − | pin 6 and ground |
| F2 — preset + | pin 7 and ground |
| F3 — tuner | pin 9 and ground |
| F4 — spare | pin 10 and ground |

Three-lug footswitches are often changeover types: use the common lug and one of
the others. Check with a multimeter which pair closes on press.

**Let the wire reach the lug slack.** The lug takes the mechanical load of the
press, transmitted through the switch body. A wire under tension on a joint
eventually fails, long before the wire itself fatigues.

---

## 6. The LEDs

One resistor **per LED**, never shared: a common resistor makes brightness vary
with how many LEDs are lit.

```
   GPx ─────[ 330 Ω ]─────▶|───── ground rail
                        anode  cathode
```

The long leg is the anode, resistor side. The short leg — and the flat on the
housing — mark the cathode, ground side.

| LED | Pin |
|---|---|
| LED 1 | 11 |
| LED 2 | 12 |
| LED 3 | 21 |
| LED 4 | 22 |
| LED 5 | 24 |
| LED 6 | 25 |
| LED 7 | 26 |
| LED 8 | 27 |

### On resistor value

With 330 Ω and a red LED, the Pico's 3.3 V output sources about 4 mA peak. The
code then applies 12 % PWM, giving deliberately low brightness.

If it's too dim on stage, two levers in this order: **raise `BRILLANCE`** in
`code.py`, which is free and reversible; only then drop to 220 Ω. Don't go below
150 Ω — a Pico pin is rated for 12 mA.

> **Blue and white LEDs are a special case.** Their forward voltage is 3.0 to
> 3.2 V, essentially the Pico's 3.3 V. They'll be very dim whatever the resistor.
> Stick to red, yellow or standard green.

### Preparing an LED

The aim: the LED leaves the bench as a two-wire component with no bare resistor
anywhere in the enclosure.

1. **Use different wire colours for the two legs.** Solid for cathode (ground),
   striped for anode. Same on all eight — once heatshrunk you'll only see wires.
2. **Cut the anode — the long leg — to 5 mm.** Leave the cathode longer so you
   can still tell them apart.
3. **Slide the heatshrink on BEFORE soldering.** Two pieces, one per joint. This
   is the mistake everyone makes once.
4. **Solder the resistor end-to-end onto the anode.** Tin both, touch them
   together, heat for a second. No twisting needed.
5. **Solder the striped wire** to the far end of the resistor, and the solid wire
   to the cathode.
6. **Shrink both sleeves.** The anode sleeve should cover the whole resistor and
   overhang each end.

---

## 7. The LCD1602

| LCD pin | To |
|---|---|
| 1 VSS | ground rail |
| 2 VDD | pin 40 — VBUS, 5 V |
| 3 V0 | potentiometer wiper |
| 4 RS | pin 14 |
| 5 R/W | **ground rail** |
| 6 E | pin 15 |
| 7–10 D0–D3 | **nothing**, 4-bit mode |
| 11 D4 | pin 16 |
| 12 D5 | pin 17 |
| 13 D6 | pin 19 |
| 14 D7 | pin 20 |
| 15 A | pin 40 — VBUS |
| 16 K | ground rail |

### Contrast potentiometer

10 kΩ, three legs. The **middle** one is the wiper.

```
   VBUS ──────┤ │ │├────── ground rail
               └─┬─┘
                 └──────── LCD pin 3
```

The two outer legs are interchangeable; swapping them only reverses the
direction of travel.

**Without it the display is either solid black or completely blank.** It's the
number one cause of "my LCD doesn't work".

### Three things that matter

**R/W must go to ground.** That puts the LCD in write-only mode so it can never
drive 5 V back into a Pico input. This is what makes the 5 V / 3.3 V mix safe
here.

**No resistor on pin 15.** QAPASS 1602A modules already carry R8, marked `101`
for 100 Ω, on the back near pin K. On another model, check before connecting —
otherwise 220 Ω in series.

**Bridge on the module.** Pins 1, 5 and 16 all go to ground: link them directly
on the LCD so only one wire leaves. Same for 2 and 15 to VBUS. That takes you
from ten wires to eight, and the potentiometer straddles pins 1, 2 and 3 with no
flying leads.

---

## 8. Mounting the Pico

Don't solder wires straight to the Pico. Solder **two female headers to the
stripboard** and plug the Pico into them. All wiring lands on the board, never on
the module.

The day you want to replace the Pico, change a pin assignment or reclaim it for
something else, it lifts straight out. Twenty wires soldered to tightly-spaced
pads means an hour of desoldering and at least one lifted pad.

Headers cost 8 mm of height. If your enclosure is tight at the front — 27 mm —
soldering the Pico flat to the board is an acceptable trade: the board itself
stays modifiable.

**Solder the headers with the Pico plugged into them.** That keeps them square.
Freehand they end up skewed and won't fit anywhere.

---

## 9. Assembly order

Test each step before moving on.

1. **The ground rail and its link to pin 38.** Check continuity end to end.
2. **VBUS.** Check there is *no* continuity between the ground rail and 5 V — a
   short here stops the Pico booting.
3. **The LCD**, potentiometer included. On power-up a row of black blocks should
   appear: proof it's alive. Turn the pot until they fade.
4. **The LEDs, one at a time.** Test each with
   `printf 'S1\n' > /dev/pipedal-pico` and variants.
5. **The switches, one at a time.** `aseqdump -p XX:0` on the Pi shows the CCs
   going out.

---

## 10. Multimeter checks

Pico unplugged, before first power-up:

| Test | Expected |
|---|---|
| Ground rail ↔ pin 38 | continuity |
| Pin 38 ↔ pin 40 | **no** continuity |
| Each LED cathode ↔ rail | continuity |
| Each LED anode ↔ its pin | ~330 Ω |
| LCD 1, 5, 16 ↔ rail | continuity |
| LCD 2, 15 ↔ pin 40 | continuity |
| Two adjacent GPIO pins | **no** continuity |

The last one catches solder bridges, which are both the most common fault and the
hardest to see by eye on stripboard.

---

## 11. Wire count

| Destination | Wires to the board |
|---|---|
| 8 switches | 8 signal + 8 ground |
| 8 LEDs | 8 signal + 8 ground |
| LCD | 6 signal + 1 ground + 1 power |
| Potentiometer | 3 |
| **Total** | **42** |

Solid-core wire pulled from Cat 6 cable (23 AWG, 0.26 mm²) works well: it handles
several amps where the build draws 50 mA, it holds in a breadboard, its
insulation survives the iron, and eight colours make identification easy.

Pick a convention and write it down — brown for ground, orange for 5 V, say. Six
months from now, reopening the enclosure, you'll be glad not to have to buzz out
every wire.
