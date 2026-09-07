# ---------------------------------------------------------------------------
# code.py - BANC DE TEST LED
#
# A copier sur le Pico de la breadboard, PAS sur celui du pedalier.
# Aucune dependance : ni bibliotheque, ni Pi, ni MIDI.
#
# Cablage : GP0 a GP7 vers l'anode (cote resistance) de chaque LED,
#           toutes les cathodes vers un rail de masse relie a GND.
#
# Trois phases en boucle :
#   1. COMPARAISON  toutes allumees a BRILLANCE, pour egaliser
#   2. DEFILEMENT   une par une, pour identifier les positions
#   3. PLEIN FEU    toutes a 100 %, pour reperer une LED morte ou inversee
# ---------------------------------------------------------------------------

import time

import board
import pwmio

BROCHES = (
    board.GP0, board.GP1, board.GP2, board.GP3,
    board.GP4, board.GP5, board.GP6, board.GP7,
)

# Recopie ici les valeurs de ton code.py, puis ajuste en regardant
# les LED cote a cote. Ce sont ces chiffres que tu reporteras ensuite.
BRILLANCE = (12, 12, 12, 12, 12, 12, 12, 12)

FREQUENCE = 2000

T_COMPARAISON = 6.0
T_PAS = 0.35            # duree d'allumage de chaque LED en defilement
T_PLEIN = 3.0


leds = [pwmio.PWMOut(b, frequency=FREQUENCE, duty_cycle=0) for b in BROCHES]


def allumer(i, pourcent):
    leds[i].duty_cycle = int(65535 * pourcent / 100)


def toutes(pourcent):
    for i in range(len(leds)):
        allumer(i, pourcent if isinstance(pourcent, int) else pourcent[i])


print()
print("=== BANC DE TEST LED ===")
print("GP0 a GP7 -> anode (cote resistance)")
print("cathodes  -> rail de masse")
print()
print("Une LED eteinte en phase 3 est morte, mal soudee, ou a l'envers.")
print()

while True:
    # --- 1. comparaison : c'est ici qu'on regle BRILLANCE ---------------
    print("1. COMPARAISON  -  toutes a BRILLANCE, cherche les ecarts")
    toutes(BRILLANCE)
    time.sleep(T_COMPARAISON)
    toutes(0)
    time.sleep(0.4)

    # --- 2. defilement : identification des positions -------------------
    print("2. DEFILEMENT   -  GP0 vers GP7")
    for i in range(len(leds)):
        allumer(i, BRILLANCE[i])
        time.sleep(T_PAS)
        allumer(i, 0)
    time.sleep(0.4)

    # --- 3. plein feu : detection des LED mortes -------------------------
    print("3. PLEIN FEU    -  toutes a 100 %")
    toutes(100)
    time.sleep(T_PLEIN)
    toutes(0)
    time.sleep(0.8)
