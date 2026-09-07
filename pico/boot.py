# ---------------------------------------------------------------------------
# boot.py - racine du lecteur CIRCUITPY
#
# 1. Active un second port CDC (data) en plus du MIDI : peripherique
#    composite MIDI + serie sur le meme cable USB.
# 2. Renomme le peripherique pour l'identifier proprement cote Pi.
#
# ATTENTION : boot.py n'est relu qu'au HARD RESET.
#             Enregistrer le fichier ne suffit pas : debranche / rebranche.
#
# Budget endpoints RP2040 : 7 paires utilisables (la paire 0 est reservee).
#   CIRCUITPY (MSC)  1
#   console CDC      2
#   data CDC         2
#   MIDI             1
#   -------------------
#   total            6   -> ca passe, avec une paire de marge.
#
# Si le Pico part en mode sans echec au demarrage : passer console=False.
# Tu perds le REPL mais tu liberes 2 paires.
# ---------------------------------------------------------------------------

import supervisor
import usb_cdc
import usb_midi

usb_midi.enable()                                # deja actif par defaut
usb_cdc.enable(console=True, data=True)          # console=False en version scene

# Nom affiche par le systeme hote (lsusb, ALSA, PiPedal).
supervisor.set_usb_identification(product="Pedalier")
usb_midi.set_names(streaming_interface_name="Switches")

# Cette ligne n'apparait PAS sur la console serie : boot.py s'execute avant
# son ouverture. Elle est ecrite dans boot_out.txt a la racine de CIRCUITPY.
print("boot.py OK - renommage applique")
