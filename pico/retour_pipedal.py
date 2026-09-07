# ---------------------------------------------------------------------------
# retour_pipedal.py - racine du lecteur CIRCUITPY, a cote de code.py
#
# Lien bidirectionnel avec le demon du Raspberry Pi, sur le port CDC data.
#
# Principe : la LED ne s'allume plus a l'appui, mais a la CONFIRMATION.
#   appui                        -> envoi du CC, armement d'une attente
#   trame "S<n>" recue           -> allumage exclusif
#   pas de reponse sous 200 ms   -> allumage quand meme (mode degrade)
#   plus de heartbeat            -> clignotement lent, le lien est mort
# ---------------------------------------------------------------------------

import time
import usb_cdc

TIMEOUT_CONFIRMATION = 0.20      # secondes avant repli optimiste
TIMEOUT_HEARTBEAT    = 3.0       # secondes sans HB avant alerte visuelle
PERIODE_CLIGNOTEMENT = 0.4       # secondes

_serie = usb_cdc.data
_tampon = b""

_afficher = None                 # callback LED exclusive (snapshots)
_led = None                      # callback LED individuelle led(i, bool)
_ecran = None                    # module ecran, ou None si absent
_nb_snapshots = 4

TIMEOUT_CHARGEMENT = 2.5         # secondes max d'attente d'un changement
_attente_preset = None           # (index_led, echeance)

PERIODE_APPEL = 1.0              # secondes entre deux demandes d'etat
_prochain_appel = 0.0

_snapshot_actif = None           # index base 0, None si inconnu
_attente = None                  # (index, echeance) pendant le repli optimiste
_dernier_hb = 0.0
_lien_ok = False
_phase = False


def init(callback_affichage, nb_snapshots, ecran=None, callback_led=None):
    """callback_affichage(index) allume la LED index en exclusif.
       callback_affichage(None) eteint le groupe.
       callback_led(index, bool) allume une LED isolee.
       ecran : module ecran deja initialise, ou None."""
    global _afficher, _nb_snapshots, _dernier_hb, _ecran, _led
    _afficher = callback_affichage
    _led = callback_led
    _nb_snapshots = nb_snapshots
    _ecran = ecran
    _dernier_hb = time.monotonic()
    if _serie is not None:
        _serie.timeout = 0       # lecture non bloquante


def appui(index):
    """A appeler depuis on_press pour un switch snapshot.
       Arme le repli optimiste, n'allume rien."""
    global _attente
    if index < _nb_snapshots:
        _attente = (index, time.monotonic() + TIMEOUT_CONFIRMATION)


def attente_changement(index_led):
    """Appui sur un switch qui change de preset. La LED reste allumee
    jusqu'a ce que le Pi annonce le nouveau nom, ou 2,5 s au plus.

    Charger un preset avec un modele NAM prend une a deux secondes :
    un simple flash se terminerait avant que quoi que ce soit ait bouge."""
    global _attente_preset
    if _led is None:
        return
    _led(index_led, True)
    _attente_preset = (index_led, time.monotonic() + TIMEOUT_CHARGEMENT)


def _fin_attente_preset():
    global _attente_preset
    if _attente_preset is None:
        return
    _led(_attente_preset[0], False)
    _attente_preset = None


def envoyer(texte):
    """Commande du Pico vers le demon. Ne leve jamais."""
    if _serie is None:
        return
    try:
        _serie.write((texte + "\n").encode("ascii"))
    except Exception:
        pass


def lien_actif():
    return _lien_ok


# ---------------------------------------------------------------------------
# ### VOCABULAIRE SERIE ###
#
# Pi -> Pico
#   S<n>              snapshot actif, base 1
#   HB                battement de coeur
#   N:<texte>         nom du pedalboard      -> ecran ligne 1
#   M:<texte>         nom du snapshot actif  -> ecran ligne 2
#   T:<note>:<cents>  accordeur, ex. T:E2:-12
#   T:-               accordeur, aucun signal
#   T:!               aucun accordeur dans le pedalboard
#
# Pico -> Pi
#   A1 / A0           entree / sortie du mode accordeur
#   ?                 demande de l'etat complet (au demarrage)
# ---------------------------------------------------------------------------

def _traiter(ligne):
    global _snapshot_actif, _attente, _dernier_hb, _lien_ok

    if not ligne:
        return

    # Toute trame recue vaut signe de vie.
    _dernier_hb = time.monotonic()
    if not _lien_ok:
        _lien_ok = True
        if _ecran is not None:
            _ecran.lien(True)

    if ligne == "HB":
        return

    if ligne[0] == "S":
        try:
            n = int(ligne[1:]) - 1        # protocole en base 1
        except ValueError:
            return
        if 0 <= n < _nb_snapshots:
            _snapshot_actif = n
            _attente = None
            _afficher(n)
            if _ecran is not None:
                _ecran.snapshot(n)
        return

    tete = ligne[:2]

    if tete == "N:":
        _fin_attente_preset()
        if _ecran is not None:
            _ecran.preset(ligne[2:])
        return

    if tete == "M:":
        if _ecran is not None:
            _ecran.snapshot(_snapshot_actif, ligne[2:])
        return

    if tete == "T:":
        if _ecran is None:
            return
        corps = ligne[2:]
        if corps == "!":
            _ecran.accordeur(None, 0, dispo=False)
        elif corps == "-":
            _ecran.accordeur(None, 0)
        else:
            try:
                note, cents = corps.split(":")
                _ecran.accordeur(note, int(cents))
            except ValueError:
                pass
        return

    # TODO : "B<n>:<0|1>" etat de bypass


# ---------------------------------------------------------------------------
# Lecture non bloquante
# ---------------------------------------------------------------------------

def _lire():
    global _tampon
    if _serie is None or _serie.in_waiting == 0:
        return
    _tampon += _serie.read(_serie.in_waiting)
    while b"\n" in _tampon:
        brut, _tampon = _tampon.split(b"\n", 1)
        try:
            _traiter(brut.decode("utf-8").strip())
        except UnicodeError:
            pass


def tick():
    """A appeler a chaque tour de la boucle principale."""
    global _attente, _lien_ok, _phase, _snapshot_actif, _prochain_appel

    _lire()
    maintenant = time.monotonic()

    # Tant que le Pi ne s'est pas manifeste, on reclame l'etat.
    # Le demon n'emet que sur changement : apres un redemarrage du Pico,
    # sans cette balise il ne dirait rien avant le prochain appui.
    if not _lien_ok and maintenant >= _prochain_appel:
        _prochain_appel = maintenant + PERIODE_APPEL
        envoyer("?")

    # Repli optimiste : le Pi n'a pas repondu, on allume quand meme.
    if _attente is not None and maintenant >= _attente[1]:
        index = _attente[0]
        _attente = None
        _snapshot_actif = index
        _afficher(index)
        if _ecran is not None:
            _ecran.snapshot(index)

    # Chargement de preset trop long : on eteint quand meme.
    if _attente_preset is not None and maintenant >= _attente_preset[1]:
        _fin_attente_preset()

    # Perte du lien : clignotement lent + marqueur a l'ecran.
    if maintenant - _dernier_hb > TIMEOUT_HEARTBEAT:
        if _lien_ok:
            _lien_ok = False
            if _ecran is not None:
                _ecran.lien(False)
        phase = int(maintenant / PERIODE_CLIGNOTEMENT) % 2 == 0
        if phase != _phase:
            _phase = phase
            _afficher(_snapshot_actif if phase else None)
