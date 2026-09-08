#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# pipedal_bridge.py - Demon de pont PiPedal -> Pico
#
# A INSTALLER SUR LE RASPBERRY PI, pas sur le Pico.
#
# Protocole PiPedal 2.0.110, releve par capture des trames websocket.
#
#   Enveloppe : tableau JSON  [entete]  ou  [entete, corps]
#
#   Requete sans argument (1 element) :
#     [{"message": "hello", "replyTo": 2}]
#   Requete avec argument (2 elements) :
#     [{"message": "monitorPort", "replyTo": 24},
#      {"instanceId": 16, "key": "FREQ", "updateRate": 0.0333}]
#   Reponse du serveur :
#     [{"reply": 2, "message": "ehlo"}, 20]
#
#   Diffusion sur changement (pas de replyTo, rien a acquitter) :
#     [{"message": "onPedalboardChanged"},
#      {"clientId": -1, "pedalboard": { ... "selectedSnapshot": 1 ... }}]
#
#   Message pousse avec accuse demande :
#     [{"replyTo": 996, "message": "onVuUpdate"}, {...}]
#   Le client doit repondre :
#     [{"reply": 996, "message": "onVuUpdate"}, true]
#
#   IMPORTANT : le client doit envoyer "hello" a la connexion pour etre
#   enregistre comme destinataire des diffusions.
#
#   L'index de snapshot est en BASE 0 cote PiPedal.
#   Le protocole serie vers le Pico est en BASE 1 (S1..S4).
#
# Protocole serie emis vers le Pico :
#   S<n>        snapshot actif, base 1
#   S-          aucun snapshot selectionne dans ce pedalboard
#   HB          battement de coeur, 1 Hz
#   N:<texte>   nom du pedalboard      -> LCD ligne 1
#   M:<texte>   nom du snapshot actif  -> LCD ligne 2
#   T:<note>:<cents>  accordeur, ex. T:E2:-12
#   T:-         accordeur, aucun signal
#   T:!         aucun accordeur dans le pedalboard
#
# Protocole serie recu du Pico :
#   A1 / A0     entree / sortie du mode accordeur
#   ?           le Pico demarre et reclame l'etat complet
#
# Dependances :
#   sudo apt install python3-serial
#   pip3 install websockets --break-system-packages
#
# Lancement :
#   python3 pipedal_bridge.py -v
# ---------------------------------------------------------------------------

import argparse
import asyncio
import json
import logging
import time

import serial
import websockets


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WS_URL = "ws://127.0.0.1:80/pipedal"      # chemin confirme par capture

PORT_SERIE = "/dev/pipedal-pico"
BAUD = 115200

PERIODE_HEARTBEAT = 1.0
BACKOFF_MIN = 0.5
BACKOFF_MAX = 10.0

# Repli si le serveur ne diffuse rien : redemander l'etat periodiquement.
# Mettre a 0 pour desactiver.
PERIODE_SONDAGE = 0.0

# Accordeur
URI_ACCORDEUR = "http://two-play.com/plugins/toob-tuner"
PORT_ACCORDEUR = "FREQ"
PERIODE_ACCORDEUR = 0.05     # secondes entre deux mesures cote PiPedal
DEBIT_ACCORDEUR = 0.09       # intervalle mini entre deux trames serie
PAS_CENTS = 2                # quantification, evite de saturer le LCD

NOTES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

log = logging.getLogger("bridge")

# Sentinelle : distingue "pas encore recu" de "aucun snapshot actif".
INCONNU = object()


# ---------------------------------------------------------------------------
# Lien serie vers le Pico
#
# Le Pico reinitialise son USB a chaque sauvegarde de code.py : le port
# disparait puis revient. Cette classe encaisse ca sans faire tomber le demon.
# ---------------------------------------------------------------------------

class LienPico:

    def __init__(self, port, baud):
        self.port = port
        self.baud = baud
        self.ser = None
        self._signale = False
        self._tampon = b""
        self._neuf = False

    def _ouvrir(self):
        if self.ser is not None:
            return True
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0)
            self.ser.dtr = True       # sans DTR, le Pico ne lit rien
            log.info("Port serie ouvert : %s", self.port)
            self._signale = False
            self._neuf = True
            return True
        except (serial.SerialException, OSError) as e:
            self.ser = None
            if not self._signale:
                log.warning("Port serie indisponible (%s)", e)
                self._signale = True
            return False

    def _fermer(self):
        if self.ser is not None:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
            log.warning("Port serie perdu, reouverture au prochain envoi")

    def reconnecte(self):
        """True une seule fois apres chaque (re)ouverture du port.

        Le Pico redemarre sans que PiPedal change d'etat : sans ce signal,
        le demon continuerait d'emettre uniquement des HB et le pedalier
        resterait aveugle jusqu'au prochain changement reel."""
        if self._neuf:
            self._neuf = False
            return True
        return False

    def lire(self):
        """Renvoie les lignes completes recues du Pico. Ne leve jamais."""
        if not self._ouvrir():
            return []
        try:
            n = self.ser.in_waiting
            if n:
                self._tampon += self.ser.read(n)
        except (serial.SerialException, OSError):
            self._fermer()
            return []

        lignes = []
        while b"\n" in self._tampon:
            brut, self._tampon = self._tampon.split(b"\n", 1)
            try:
                texte = brut.decode("ascii").strip()
            except UnicodeDecodeError:
                continue
            if texte:
                lignes.append(texte)
        return lignes

    def envoyer(self, trame):
        """Envoie une trame texte, saut de ligne ajoute. Ne leve jamais."""
        if not self._ouvrir():
            return False
        try:
            self.ser.write((trame + "\n").encode("ascii"))
            return True
        except (serial.SerialException, OSError):
            self._fermer()
            return False


# ---------------------------------------------------------------------------
# Etat courant, cache pour n'emettre que sur changement
# ---------------------------------------------------------------------------

class Etat:

    def __init__(self, lien):
        self.lien = lien
        # None      : aucun snapshot selectionne cote PiPedal
        # INCONNU   : on n'a pas encore recu l'information
        self.snapshot = INCONNU        # index base 0, ou None
        self.nom_pedalboard = None
        self.nom_snapshot = None
        self.instance = None       # instanceId du TooB Tuner
        self.mode_accordeur = False
        self.handle = None         # subscriptionHandle renvoye par PiPedal
        self.attente_handle = None # replyTo de notre monitorPort en cours
        self.compteur = 100
        self._derniere_note = None
        self._dernier_envoi = 0.0

    def maj_snapshot(self, index_base0, forcer=False):
        """index_base0 : index PiPedal, base 0.

        PiPedal renvoie -1 quand le pedalboard n'a aucun snapshot
        selectionne. Sans traitement dedie, le +1 donnerait S0, que le
        Pico rejetterait en silence en gardant l'ancien affichage."""
        if index_base0 is None:
            return                       # information absente : on ne touche a rien

        index = int(index_base0)
        if index < 0:
            index = None                 # aucun snapshot actif

        if not forcer and index == self.snapshot:
            return
        self.snapshot = index

        if index is None:
            self.lien.envoyer("S-")
            log.info("snapshot -> aucun")
        else:
            self.lien.envoyer("S%d" % (index + 1))
            log.info("snapshot -> %d", index + 1)

    def maj_nom(self, nom, forcer=False):
        if not nom:
            return
        if forcer or nom != self.nom_pedalboard:
            self.nom_pedalboard = nom
            # Le Pico ignore cette trame pour l'instant. Elle servira
            # quand un ecran sera cable.
            self.lien.envoyer("N:" + nom[:20])
            log.info("pedalboard -> %s", nom)

    def maj_nom_snapshot(self, nom, forcer=False):
        if not nom:
            return
        if forcer or nom != self.nom_snapshot:
            self.nom_snapshot = nom
            self.lien.envoyer("M:" + nom[:16])
            log.info("snapshot nomme -> %s", nom)

    # -- accordeur -----------------------------------------------------

    def _id(self):
        self.compteur += 1
        return self.compteur

    async def abonner(self, ws):
        """S'abonne au port FREQ du TooB Tuner du pedalboard courant."""
        if self.instance is None:
            self.lien.envoyer("T:!")
            log.warning("Aucun TooB Tuner dans ce pedalboard")
            return
        ident = self._id()
        self.attente_handle = ident
        await ws.send(trame_requete(ident, "monitorPort", {
            "instanceId": self.instance,
            "key": PORT_ACCORDEUR,
            "updateRate": PERIODE_ACCORDEUR,
        }))
        log.info("Accordeur : abonnement sur instance %s", self.instance)

    async def desabonner(self, ws):
        if self.handle is None:
            return
        await ws.send(json.dumps([{"message": "unmonitorPort"}, self.handle]))
        log.info("Accordeur : desabonnement")
        self.handle = None
        self.attente_handle = None
        self._derniere_note = None

    async def activer(self, ws, actif):
        if actif == self.mode_accordeur:
            return
        self.mode_accordeur = actif
        if actif:
            await self.abonner(ws)
        else:
            await self.desabonner(ws)

    def mesure(self, valeur):
        """Traduit une valeur FREQ en trame serie, avec limitation de debit."""
        if not self.mode_accordeur:
            return

        note, cents = note_et_cents(valeur)
        if note is not None:
            cents = int(round(cents / PAS_CENTS)) * PAS_CENTS
        courant = (note, cents)

        maintenant = time.monotonic()
        if courant == self._derniere_note:
            return
        if maintenant - self._dernier_envoi < DEBIT_ACCORDEUR:
            return

        self._derniere_note = courant
        self._dernier_envoi = maintenant
        if note is None:
            self.lien.envoyer("T:-")
        else:
            self.lien.envoyer("T:%s:%d" % (note, cents))

    def repousser(self):
        """Reemet l'etat connu, apres reconnexion."""
        if self.snapshot is not INCONNU:
            self.maj_snapshot(-1 if self.snapshot is None else self.snapshot,
                              forcer=True)
        if self.nom_pedalboard is not None:
            self.maj_nom(self.nom_pedalboard, forcer=True)
        if self.nom_snapshot is not None:
            self.maj_nom_snapshot(self.nom_snapshot, forcer=True)


# ---------------------------------------------------------------------------
# Protocole PiPedal
# ---------------------------------------------------------------------------

def analyser(brut):
    """Decoupe l'enveloppe. Renvoie (nom, corps, entete)."""
    try:
        paquet = json.loads(brut)
    except (ValueError, TypeError):
        return (None, None, {})

    if not isinstance(paquet, list) or not paquet:
        return (None, None, {})

    entete = paquet[0]
    if not isinstance(entete, dict):
        return (None, None, {})

    corps = paquet[1] if len(paquet) > 1 else None
    return (entete.get("message"), corps, entete)


def trame_requete(identifiant, nom, argument=None):
    """Requete client -> serveur. Un seul element si pas d'argument."""
    entete = {"message": nom, "replyTo": identifiant}
    if argument is None:
        return json.dumps([entete])
    return json.dumps([entete, argument])


def trame_accuse(identifiant, nom):
    """Accuse de reception d'un message pousse par le serveur."""
    return json.dumps([{"reply": identifiant, "message": nom}, True])


def note_et_cents(valeur):
    """FREQ du TooB Tuner : numero de note MIDI flottant, -1 si silence."""
    if valeur is None or valeur < 0:
        return (None, 0)
    entier = int(round(valeur))
    cents = int(round((valeur - entier) * 100))
    if not (0 <= entier <= 127):
        return (None, 0)
    return (NOTES[entier % 12] + str(entier // 12 - 1), cents)


def instance_accordeur(pedalboard):
    """InstanceId du TooB Tuner dans le pedalboard courant, ou None.

    Il change d'un pedalboard a l'autre : ne jamais coder 16 en dur."""
    items = pedalboard.get("items")
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and item.get("uri") == URI_ACCORDEUR:
            return item.get("instanceId")
    return None


def nom_du_snapshot(pedalboard):
    """Nom du snapshot selectionne. La liste contient des trous (null)."""
    index = pedalboard.get("selectedSnapshot")
    liste = pedalboard.get("snapshots")
    if index is None or not isinstance(liste, list):
        return None
    if not (0 <= index < len(liste)):
        return None
    entree = liste[index]
    if not isinstance(entree, dict):
        return None
    return entree.get("name")


def extraire(nom, corps):
    """
    Traduit un message en dict d'etat.
    Cles possibles : "snapshot" (base 0), "nom", "nom_snapshot".
    Renvoie {} si le message ne nous concerne pas.
    """
    if nom in ("onVuUpdate", "onMonitorPortOutput"):
        return {}

    # Diffusion sur changement : l'index est dans body.pedalboard
    if nom == "onPedalboardChanged":
        if not isinstance(corps, dict):
            return {}
        pb = corps.get("pedalboard")
        if not isinstance(pb, dict):
            return {}
        return {
            "snapshot": pb.get("selectedSnapshot"),
            "nom": pb.get("name"),
            "nom_snapshot": nom_du_snapshot(pb),
            "instance": instance_accordeur(pb),
        }

    # Reponse a notre requete : le pedalboard est a la racine du corps
    if nom == "currentPedalboard":
        if not isinstance(corps, dict):
            return {}
        return {
            "snapshot": corps.get("selectedSnapshot"),
            "nom": corps.get("name"),
            "nom_snapshot": nom_du_snapshot(corps),
            "instance": instance_accordeur(corps),
        }

    return {}


# ---------------------------------------------------------------------------
# Boucles asynchrones
# ---------------------------------------------------------------------------

async def battement(lien, etat):
    """Signal de vie vers le Pico. Son absence fait clignoter les LED.

    Sert aussi a detecter le redemarrage du Pico, pour lui renvoyer
    l'etat complet."""
    while True:
        lien.envoyer("HB")
        if lien.reconnecte():
            log.info("Pico (re)connecte : renvoi de l'etat complet")
            etat.repousser()
        await asyncio.sleep(PERIODE_HEARTBEAT)


async def ecouter_pico(lien, file):
    """Remonte les commandes envoyees par le Pico sur le port serie."""
    while True:
        for ligne in lien.lire():
            log.debug("Pico -> %s", ligne)
            await file.put(ligne)
        await asyncio.sleep(0.02)


async def commandes(ws, etat, file):
    """Applique les commandes du Pico sur la connexion courante."""
    while True:
        cmd = await file.get()
        if cmd == "A1":
            await etat.activer(ws, True)
        elif cmd == "A0":
            await etat.activer(ws, False)
        elif cmd == "?":
            # Le Pico vient de demarrer : il est forcement en mode normal.
            # Sans ce desabonnement, un reflashage effectue en mode
            # accordeur laisserait le demon abonne a FREQ pour rien.
            log.info("Le Pico reclame l'etat")
            await etat.activer(ws, False)
            etat.repousser()


async def sondage(ws):
    """Repli optionnel : redemander l'etat au lieu d'attendre la diffusion."""
    ident = 1000
    while True:
        await asyncio.sleep(PERIODE_SONDAGE)
        ident += 1
        try:
            await ws.send(trame_requete(ident, "currentPedalboard"))
        except Exception:
            return


async def session(etat, file):
    """Une connexion websocket, de l'ouverture a la coupure."""
    async with websockets.connect(WS_URL, ping_interval=20,
                                  max_size=8 * 1024 * 1024) as ws:
        log.info("Connecte a %s", WS_URL)

        # Sans ce "hello", le serveur ne nous enregistre pas comme client
        # et ne nous enverra aucune diffusion.
        await ws.send(trame_requete(1, "hello"))

        # Etat initial, sinon on reste aveugle jusqu'au premier changement.
        await ws.send(trame_requete(2, "currentPedalboard"))

        etat.repousser()

        # Une nouvelle connexion invalide l'ancien abonnement.
        etat.handle = None
        etat.attente_handle = None
        if etat.mode_accordeur:
            await etat.abonner(ws)

        taches = [asyncio.create_task(commandes(ws, etat, file))]
        if PERIODE_SONDAGE > 0:
            taches.append(asyncio.create_task(sondage(ws)))
            log.info("Sondage actif (%.2f s)", PERIODE_SONDAGE)

        try:
            async for brut in ws:
                nom, corps, entete = analyser(brut)
                if nom is None:
                    continue

                # Certains messages exigent un accuse, sinon le serveur
                # considere le client bloque et cesse d'emettre.
                ident = entete.get("replyTo")
                if ident is not None:
                    await ws.send(trame_accuse(ident, nom))

                # Reponse a notre monitorPort : on recupere le handle.
                if (nom == "monitorPort"
                        and etat.attente_handle is not None
                        and entete.get("reply") == etat.attente_handle):
                    etat.handle = corps
                    etat.attente_handle = None
                    log.info("Accordeur : handle %s", corps)
                    continue

                # Mesure de l'accordeur.
                if nom == "onMonitorPortOutput":
                    if (isinstance(corps, dict)
                            and corps.get("subscriptionHandle") == etat.handle):
                        etat.mesure(corps.get("value"))
                    continue

                champs = extraire(nom, corps)
                if not champs:
                    if nom != "onVuUpdate":
                        log.debug("<- %s", nom)
                    continue

                log.debug("<- %s %s", nom, champs)
                etat.maj_snapshot(champs.get("snapshot"))
                etat.maj_nom(champs.get("nom"))
                etat.maj_nom_snapshot(champs.get("nom_snapshot"))

                # Le TooB Tuner peut changer d'instanceId avec le pedalboard.
                instance = champs.get("instance")
                if instance != etat.instance:
                    etat.instance = instance
                    if etat.mode_accordeur:
                        etat.handle = None
                        await etat.abonner(ws)
        finally:
            for t in taches:
                t.cancel()


async def principale():
    lien = LienPico(PORT_SERIE, BAUD)
    etat = Etat(lien)

    file = asyncio.Queue()
    asyncio.create_task(battement(lien, etat))
    asyncio.create_task(ecouter_pico(lien, file))

    backoff = BACKOFF_MIN
    while True:
        try:
            await session(etat, file)
            log.warning("Websocket ferme par le serveur")
            backoff = BACKOFF_MIN
        except Exception as e:
            log.warning("Connexion perdue (%s), nouvel essai dans %.1f s",
                        e, backoff)

        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, BACKOFF_MAX)


def main():
    ap = argparse.ArgumentParser(description="Pont PiPedal vers pedalier Pico")
    ap.add_argument("-v", "--verbeux", action="store_true",
                    help="affiche le detail des trames")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbeux else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
    )
    if args.verbeux:
        logging.getLogger("websockets").setLevel(logging.INFO)

    try:
        asyncio.run(principale())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
