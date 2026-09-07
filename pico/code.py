# ---------------------------------------------------------------------------
# code.py - Pedalier MIDI PiPedal
#
# 8 footswitches / 8 LEDs / 1 afficheur LCD1602.
#   S1..S4 : snapshots, CC 102..105, LED en selection exclusive
#   F1/F2  : preset precedent / suivant, CC 110 et 111, LED pendant le
#            chargement
#   F3     : bascule accordeur, CC 112, LED allumee tant que le mode dure
#   F4     : generique, CC 113, LED en flash de confirmation
#
# Les LED des snapshots ne sont PAS allumees a l'appui : elles attendent
# la confirmation du Raspberry Pi (module retour_pipedal). Repli optimiste
# a 200 ms si le Pi ne repond pas.
# ---------------------------------------------------------------------------

import time

import board
import digitalio
import pwmio
import usb_midi
import adafruit_midi
from adafruit_midi.control_change import ControlChange

import ecran
import retour_pipedal as retour


# ---------------------------------------------------------------------------
# Configuration materielle
#
# GP0..GP7   switches
# GP8, GP9   LED 1 et 2          (cablage existant, ne pas deplacer)
# GP10..GP15 LCD1602 en 4 bits
# GP16..GP21 LED 3 a 8
# ---------------------------------------------------------------------------

# Ordre : S1, S2, S3, S4, F1, F2, F3, F4
BROCHES_SWITCHES = (
    board.GP0, board.GP1, board.GP2, board.GP3,
    board.GP4, board.GP5, board.GP6, board.GP7,
)

BROCHES_LEDS = (
    board.GP8,  board.GP9,  board.GP16, board.GP17,
    board.GP18, board.GP19, board.GP20, board.GP21,
)

# Egalisation logicielle par canal, en pourcentage de duty.
# BRILLANCE[i] s'applique a BROCHES_LEDS[i] : garder le meme ordre.
BRILLANCE = (12, 12, 12, 12, 12, 12, 12, 12)

# LCD1602 en mode 4 bits. R/W du LCD doit etre cable a la masse.
LCD_RS = board.GP10
LCD_EN = board.GP11
LCD_D4 = board.GP12
LCD_D5 = board.GP13
LCD_D6 = board.GP14
LCD_D7 = board.GP15

FREQUENCE_PWM = 2000        # Hz, au-dessus du seuil de scintillement

NB_SNAPSHOTS = 4            # S1..S4
NB_SWITCHES = 8

CC_SNAPSHOTS = (102, 103, 104, 105)
CC_GENERIQUES = (110, 111, 112, 113)
CANAL_MIDI = 0              # canal 1 en notation humaine

ANTIREBOND = 0.02           # secondes
DUREE_FLASH = 0.12          # secondes, confirmation visuelle F2..F4

# Rang arriere, de gauche a droite :
#   F1  preset precedent   CC 110
#   F2  preset suivant     CC 111
#   F3  accordeur          CC 112
#   F4  libre              CC 113
#
# A lier dans PiPedal :
#   prevProgram -> CC 110      nextProgram -> CC 111
# Optionnel : CC 112 sur le MUTE du TooB Tuner, pour couper le son et
# afficher l'accordeur d'un seul geste.

# LED allumee pendant le chargement, qui peut durer une a deux secondes
# avec un modele NAM.
SWITCHES_PRESET = (4, 5)

# LED allumee tant que le mode accordeur dure, au lieu de flasher.
SWITCH_ACCORDEUR = 6


# ---------------------------------------------------------------------------
# MIDI
# ---------------------------------------------------------------------------

midi = adafruit_midi.MIDI(
    midi_out=usb_midi.ports[1],
    out_channel=CANAL_MIDI,
)


# ---------------------------------------------------------------------------
# LEDs
# ---------------------------------------------------------------------------

_leds = []
for broche in BROCHES_LEDS:
    _leds.append(pwmio.PWMOut(broche, frequency=FREQUENCE_PWM, duty_cycle=0))


def led(index, allumee):
    """Allume ou eteint une LED, a la brillance calibree du canal."""
    if allumee:
        _leds[index].duty_cycle = int(65535 * BRILLANCE[index] / 100)
    else:
        _leds[index].duty_cycle = 0


def allumer_exclusif(index):
    """Selection exclusive sur S1..S4. index=None eteint le groupe."""
    for i in range(NB_SNAPSHOTS):
        led(i, index is not None and i == index)


def eteindre_tout():
    for i in range(NB_SWITCHES):
        led(i, False)


# ---------------------------------------------------------------------------
# Switches
# ---------------------------------------------------------------------------

_switches = []
for broche in BROCHES_SWITCHES:
    sw = digitalio.DigitalInOut(broche)
    sw.direction = digitalio.Direction.INPUT
    sw.pull = digitalio.Pull.UP          # actif a l'etat bas
    _switches.append(sw)

_etat_switch = [True] * NB_SWITCHES      # True = relache (pull-up)
_dernier_changement = [0.0] * NB_SWITCHES
_fin_flash = [0.0] * NB_SWITCHES
_mode_accordeur = False


def cc_du_switch(index):
    if index < NB_SNAPSHOTS:
        return CC_SNAPSHOTS[index]
    return CC_GENERIQUES[index - NB_SNAPSHOTS]


def on_press(index):
    """Appui detecte."""
    global _mode_accordeur

    midi.send(ControlChange(cc_du_switch(index), 127))

    if index < NB_SNAPSHOTS:
        # On n'allume PAS ici. On arme l'attente de confirmation du Pi.
        retour.appui(index)
        return

    if index in SWITCHES_PRESET:
        # La LED s'eteindra quand le Pi annoncera le nouveau nom.
        retour.attente_changement(index)
        return

    if index == SWITCH_ACCORDEUR:
        # Bascule locale. Le demon s'abonne ou se desabonne du port FREQ.
        _mode_accordeur = not _mode_accordeur
        led(index, _mode_accordeur)
        retour.envoyer("A1" if _mode_accordeur else "A0")
        ecran.mode_accordeur(_mode_accordeur)
        return

    # F2..F4 : flash local, aucun etat a synchroniser.
    led(index, True)
    _fin_flash[index] = time.monotonic() + DUREE_FLASH


def on_release(index):
    """Relachement. Indispensable : PiPedal exige un CC 0 pour re-armer
    un binding en 'Trigger on rising edge'."""
    midi.send(ControlChange(cc_du_switch(index), 0))


def scruter():
    """Lecture antirebond des 8 switches."""
    maintenant = time.monotonic()
    for i in range(NB_SWITCHES):
        niveau = _switches[i].value
        if niveau == _etat_switch[i]:
            continue
        if maintenant - _dernier_changement[i] < ANTIREBOND:
            continue

        _etat_switch[i] = niveau
        _dernier_changement[i] = maintenant

        if niveau is False:          # front descendant = appui
            on_press(i)
        else:
            on_release(i)


def entretenir_flash():
    maintenant = time.monotonic()
    for i in range(NB_SNAPSHOTS, NB_SWITCHES):
        if i == SWITCH_ACCORDEUR or i in SWITCHES_PRESET:
            continue
        if _fin_flash[i] and maintenant >= _fin_flash[i]:
            _fin_flash[i] = 0.0
            led(i, False)


# ---------------------------------------------------------------------------
# Demarrage
# ---------------------------------------------------------------------------

eteindre_tout()

# L'ecran est un confort : s'il ne repond pas, le pedalier fonctionne
# quand meme, on passe simplement None a retour.init().
ecran_ok = ecran.init(LCD_RS, LCD_EN, LCD_D4, LCD_D5, LCD_D6, LCD_D7)

# Le Pico ne decide plus de l'etat initial : il attend que le Pi le lui
# annonce. Les LED restent eteintes tant qu'aucune trame n'est arrivee.
retour.init(allumer_exclusif, NB_SNAPSHOTS,
            ecran if ecran_ok else None,
            callback_led=led)


# ---------------------------------------------------------------------------
# Boucle principale
# ---------------------------------------------------------------------------

while True:
    scruter()
    entretenir_flash()
    retour.tick()
    if ecran_ok:
        ecran.splash_tick()      # ne fait rien une fois l'animation finie
    time.sleep(0.002)
