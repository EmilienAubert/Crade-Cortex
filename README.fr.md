# Crade Cortex

[English](README.md) · **Français**

Pédalier MIDI DIY pour [PiPedal](https://github.com/rerdavies/pipedal), avec
**retour d'état** : les LED et l'écran n'affichent pas ce que le pied a demandé,
ils affichent ce que le Raspberry Pi a confirmé.

Un Pico sous CircuitPython envoie des commandes MIDI. Un démon Python sur le Pi
s'abonne au websocket de PiPedal et renvoie l'état sur le même câble USB. Un seul
état existe — celui de PiPedal — et toute la classe de bugs de désynchronisation
disparaît par construction.

> **English summary.** A DIY MIDI footswitch controller for PiPedal, with
> closed-loop state feedback over the same USB cable that carries MIDI. Includes
> [documentation of PiPedal's undocumented internal websocket
> protocol](docs/PROTOCOLE.md), reverse-engineered from version 2.0.110 — likely
> the most reusable part of this repository for other projects.

---

## Ce que ça fait

- **4 snapshots** avec sélection exclusive, confirmée par le Pi
- **Changement de preset** avec LED maintenue pendant le chargement du modèle NAM
- **Accordeur** sur l'écran, note et écart en cents, abonnement à la demande
- **LCD 16×2** : nom du pedalboard et du snapshot actif, animation au démarrage
- **Détection de lien mort** : LED clignotantes et marqueur à l'écran

```
              MIDI CC 102-113 (USB MIDI -> ALSA)
        ┌──────────────────────────────────────────────┐
        │                                              ▼
   ┌─────────┐          ┌──────────────────┐      ┌──────────┐
   │ Pédalier│◄────────►│ pipedal_bridge.py│◄─────│ pipedald │
   │  Pico   │  série   │      (démon)     │  ws  │ (PiPedal)│
   └─────────┘          └──────────────────┘      └──────────┘
    S3  N:  T:              A1  A0  ?
```

Le MIDI ne passe **pas** par le démon : le Pico parle directement à `pipedald`
via ALSA. Le démon ne s'occupe que du retour.

---

## Matériel

| Élément | Détail |
|---|---|
| Contrôleur | Raspberry Pi Pico (RP2040), CircuitPython |
| Hôte | Raspberry Pi, PiPedal 2.0.110 |
| Afficheur | LCD1602 HD44780, mode 4 bits |
| Switches | 8 footswitches SPST momentanés |
| LED | 8, PWM 2 kHz, une résistance chacune |

Câblage complet, brochage et ordre de montage : **[docs/CABLAGE.md](docs/CABLAGE.md)**

---

## Installation

### Sur le Pico

#### 1. Installer CircuitPython

Télécharger le fichier `.uf2` pour le Raspberry Pi Pico sur
[circuitpython.org](https://circuitpython.org/board/raspberry_pi_pico/).

Maintenir le bouton **BOOTSEL** enfoncé **avant** de brancher l'USB, et le
relâcher une fois branché. Un lecteur `RPI-RP2` apparaît. Y glisser le `.uf2` :
le Pico redémarre tout seul et un lecteur `CIRCUITPY` prend sa place.

Si le Pico portait un autre firmware, ou si la version majeure change,
l'installation peut laisser un système de fichiers incohérent. Dans ce cas,
passer d'abord [`flash_nuke.uf2`](https://learn.adafruit.com/circuitpython-with-raspberry-pi-pico/resetting-flash)
pour effacer complètement la mémoire.

#### 2. Installer les bibliothèques

Télécharger le [bundle CircuitPython](https://circuitpython.org/libraries) —
**celui qui correspond à la version majeure installée**. Un bundle 9.x sur un
firmware 10.x provoque des erreurs d'import difficiles à diagnostiquer. La
version se lit dans `boot_out.txt`, à la racine du `CIRCUITPY`.

Copier ces deux dossiers dans `/lib` :

```
lib/
  adafruit_midi/              MIDI USB
  adafruit_character_lcd/     pilote HD44780
```

Dossiers entiers, pas seulement les `.py` qu'on croit utiles.

#### 3. Copier le projet

À la racine du `CIRCUITPY` :

```
boot.py  code.py  ecran.py  retour_pipedal.py
```

Sous Linux, faire `sync` avant de débrancher. Le système de fichiers du
`CIRCUITPY` est petit et se corrompt facilement si l'écriture n'est pas terminée.

#### 4. Redémarrer

`boot.py` n'est relu qu'au **hard reset** : débrancher et rebrancher. Enregistrer
le fichier ne suffit pas — c'est le piège classique.

Enregistrer `code.py`, en revanche, relance le programme automatiquement.

#### Vérifier

`boot_out.txt` contient la version de CircuitPython et, en cas de problème, la
raison du passage en mode sans échec. C'est le premier endroit à regarder si
l'écran reste noir ou si rien ne démarre.

```bash
ls /dev/ttyACM*        # deux ports doivent apparaitre : console et data
```

### Sur le Raspberry Pi

```bash
sudo apt install python3-serial
pip3 install websockets --break-system-packages
```

Règle udev pour un nom de port stable — sans elle, le numéro de `ttyACM` change
selon l'ordre de branchement :

```
# /etc/udev/rules.d/99-pipedal-pico.rules
SUBSYSTEM=="tty", ATTRS{idVendor}=="239a", ATTRS{product}=="Pedalier", \
  ENV{ID_USB_INTERFACE_NUM}=="02", SYMLINK+="pipedal-pico"
```

```bash
sudo udevadm control --reload && sudo udevadm trigger
python3 pi/pipedal_bridge.py -v
```

Un exemple d'unité systemd est fourni dans la documentation.

### Bindings MIDI dans PiPedal

| Symbole système | CC |
|---|---|
| `snapshot1` … `snapshot4` | 102 … 105 |
| `prevProgram` | 110 |
| `nextProgram` | 111 |

Le CC 112 pilote l'accordeur localement. Le lier au contrôle `MUTE` du TooB Tuner
permet de couper le son et d'afficher l'accordeur d'un seul geste.

---

## Documentation

| Document | Contenu |
|---|---|
| [docs/PROTOCOLE.md](docs/PROTOCOLE.md) | **Le protocole websocket de PiPedal**, reverse-engineeré |
| [docs/CABLAGE.md](docs/CABLAGE.md) | Brochage, câblage, ordre de montage, vérifications |
| [docs/index.fr.html](docs/index.fr.html) | Documentation complète, mise en page |

---

## Le principe

> PiPedal est la seule source de vérité. Le Pico n'a pas d'état propre.

L'appui envoie un CC, rien de plus. La LED ne s'allume qu'à réception de la
confirmation du Pi. C'est ce qui rend l'affichage juste quel que soit l'origine
du changement — le pied, le téléphone, ou un redémarrage de `pipedald`.

Deux garde-fous couvrent l'échec du lien, parce qu'une boucle fermée qui s'ouvre
laisserait les LED figées sur la dernière valeur reçue :

- **Repli optimiste à 200 ms** — sans confirmation, la LED s'allume quand même.
  Mode dégradé, mais jouable.
- **Heartbeat à 1 Hz** — trois battements manqués et la LED active clignote,
  un `!` apparaît à l'écran.

---

## Protocole série

Une ligne ASCII par événement, bidirectionnel.

| Sens | Trame | Signification |
|---|---|---|
| Pi → Pico | `S<n>` | Snapshot actif, base 1 |
| | `HB` | Battement de cœur |
| | `N:<texte>` | Nom du pedalboard |
| | `M:<texte>` | Nom du snapshot |
| | `T:<note>:<cents>` | Accordeur |
| Pico → Pi | `A1` / `A0` | Entrée / sortie du mode accordeur |
| | `?` | Demande de l'état complet |

La balise `?` mérite une explication : le démon met l'état en cache et n'émet que
sur changement. Quand le Pico redémarre, rien n'a changé côté PiPedal — sans
cette demande explicite, le pédalier resterait aveugle jusqu'au prochain
changement réel.

---

## Outils

`outils/banc_test_led.py` — banc de test à copier sur un second Pico. Trois
phases en boucle : comparaison à la brillance réelle pour égaliser les canaux,
défilement pour identifier les positions, plein feu pour repérer une LED morte ou
inversée.

---

## Avertissement sur le protocole websocket

L'API websocket de PiPedal est **interne et non documentée**. Ce dépôt en publie
une description relevée par capture sur la version **2.0.110**. Elle changera
d'une version à l'autre, sans préavis et sans que ce soit un bug côté PiPedal.

Si tu construis dessus, épingle-toi à une version connue et prévois de
revérifier après chaque mise à jour.

---

## Licence

MIT. Voir [LICENSE](LICENSE).

Développé avec l'assistance de Claude (Anthropic). L'architecture, le
reverse-engineering du protocole et les arbitrages techniques sont le fruit d'un
travail itératif entre humain et modèle.

---

## Remerciements

[Robin Davies](https://github.com/rerdavies) pour PiPedal, qui fait tourner un
processeur d'effets sérieux sur un Raspberry Pi et dont l'architecture — un
modèle unique côté serveur, diffusé à tous les clients — rend ce genre de projet
possible.
