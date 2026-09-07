# ---------------------------------------------------------------------------
# ecran.py - Afficheur LCD1602 (HD44780) en mode 4 bits
#
# A copier a la racine du lecteur CIRCUITPY.
# Dependance : dossier adafruit_character_lcd/ dans /lib.
#
# Trois etats d'affichage.
#
#   Demarrage           Normal              Accordeur
#   +----------------+  +----------------+  +----------------+
#   |  CRADE CORTEX  |  |Fender Clean    |  |      E2   -12c |
#   |##########      |  |2 Chorus        |  |.......|#|......|
#   +----------------+  +----------------+  +----------------+
#
# La barre de demarrage n'est pas decorative : elle progresse tant que le
# Pi n'a pas parle, et ne se remplit qu'a la premiere trame recue. Si le
# demon ne tourne pas, elle bat sur place au lieu de mentir.
#
# Le LCD conserve son affichage tout seul : on n'ecrit que sur changement.
# Une ecriture de ligne coute environ 10 ms pendant lesquelles la boucle
# principale est bloquee, d'ou le cache par ligne.
# ---------------------------------------------------------------------------

import time

import digitalio
import adafruit_character_lcd.character_lcd as characterlcd

COLONNES = 16
LIGNES = 2

JUSTE = 4          # tolerance en cents pour afficher "OK"
PLAGE = 50         # cents represente par une demi-barre

# --- animation de demarrage ---
#
# Les lettres apparaissent une par une et ne bougent plus ensuite.
# Un LCD a cristaux liquides met 150 a 250 ms a basculer un pixel : tout
# mouvement continu se transforme en bouillie. Une apparition fixe reste
# nette, parce qu'aucun cristal n'a besoin de revenir en arriere.
TITRE = "CRADE CORTEX"
COL_TITRE = 2                        # (16 - 12) / 2

T_LETTRE = 0.1                       # apparition d'une lettre
T_TITRE  = T_LETTRE * len(TITRE)     # 1,2 s pour le titre complet
T_PAUSE  = 0.25                      # temps mort avant la barre
T_BARRE  = 1.60    # duree de remplissage jusqu'au palier
T_FINAL  = 0.35    # maintien de la barre pleine avant de rendre la main

SOUS_CASES = 5                       # colonnes de pixels par caractere
TOTAL = COLONNES * SOUS_CASES        # 80 pas de barre
PALIER = TOTAL - 5                   # on n'atteint pas 100 % sans le Pi

_lcd = None
_cache = [None, None]

_nom_pedalboard = ""
_index_snapshot = None
_nom_snapshot = ""
_lien_ok = True

_mode_accordeur = False
_note = None
_cents = 0
_accordeur_dispo = True

_splash = False        # animation en cours
_splash_t0 = 0.0
_splash_pret = False   # le Pi a parle
_splash_plein = 0.0    # instant ou la barre a atteint 100 %


# ---------------------------------------------------------------------------
# Le HD44780 (ROM A00) ne connait pas les accents : on les replie sur ASCII.
# ---------------------------------------------------------------------------

_ACCENTS = {
    "\u00e0": "a", "\u00e2": "a", "\u00e4": "a",
    "\u00e9": "e", "\u00e8": "e", "\u00ea": "e", "\u00eb": "e",
    "\u00ee": "i", "\u00ef": "i",
    "\u00f4": "o", "\u00f6": "o",
    "\u00f9": "u", "\u00fb": "u", "\u00fc": "u",
    "\u00e7": "c",
    "\u00c0": "A", "\u00c2": "A",
    "\u00c9": "E", "\u00c8": "E", "\u00ca": "E",
    "\u00ce": "I", "\u00cf": "I",
    "\u00d4": "O", "\u00d9": "U", "\u00db": "U",
    "\u00c7": "C",
}


def _propre(texte):
    sortie = ""
    for c in texte:
        c = _ACCENTS.get(c, c)
        code = ord(c)
        sortie += c if 32 <= code <= 126 else " "
    return sortie


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init(broche_rs, broche_en, broche_d4, broche_d5, broche_d6, broche_d7):
    """Cable le LCD et lance l'animation. True si l'ecran repond.

    Un echec ici ne doit jamais empecher le pedalier de fonctionner :
    l'ecran est un confort, les LED sont l'essentiel."""
    global _lcd
    try:
        rs = digitalio.DigitalInOut(broche_rs)
        en = digitalio.DigitalInOut(broche_en)
        d4 = digitalio.DigitalInOut(broche_d4)
        d5 = digitalio.DigitalInOut(broche_d5)
        d6 = digitalio.DigitalInOut(broche_d6)
        d7 = digitalio.DigitalInOut(broche_d7)

        _lcd = characterlcd.Character_LCD_Mono(
            rs, en, d4, d5, d6, d7, COLONNES, LIGNES
        )
        _lcd.clear()
        _creer_blocs()
        _demarrer_splash()
        return True
    except Exception:
        _lcd = None
        return False


def _creer_blocs():
    """Cinq caracteres personnalises : 1 a 5 colonnes de pixels allumees.

    Ils donnent une barre de progression fluide de 80 pas au lieu des 16
    que permettraient de simples blocs pleins.

    L'emplacement 0 est laisse libre : chr(0) termine une chaine et se
    comporte mal avec la bibliotheque."""
    for n in range(1, SOUS_CASES + 1):
        motif = (0b11111 << (SOUS_CASES - n)) & 0b11111
        _lcd.create_char(n, [motif] * 8)


# ---------------------------------------------------------------------------
# Ecriture
# ---------------------------------------------------------------------------

def _ecrire(ligne, texte, brut=False):
    """Ecrit une ligne, completee a 16 caracteres. Rien si identique.
       brut=True court-circuite la translitteration (barre de progression)."""
    if _lcd is None:
        return
    if not brut:
        texte = _propre(texte)
    texte = texte[:COLONNES]
    texte += " " * (COLONNES - len(texte))
    if _cache[ligne] == texte:
        return
    _cache[ligne] = texte
    try:
        _lcd.cursor_position(0, ligne)
        _lcd.message = texte
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Animation de demarrage
# ---------------------------------------------------------------------------

def _demarrer_splash():
    global _splash, _splash_t0, _splash_pret, _splash_plein
    _splash = True
    _splash_t0 = time.monotonic()
    _splash_pret = False
    _splash_plein = 0.0


def _titre_partiel(n):
    """Les n premieres lettres du titre, a leur place definitive."""
    n = max(0, min(len(TITRE), int(n)))
    return " " * COL_TITRE + TITRE[:n]


def _barre_progression(pas):
    """pas de 0 a 80. Rendu fluide grace aux caracteres personnalises."""
    pas = max(0, min(TOTAL, int(pas)))
    pleines = pas // SOUS_CASES
    reste = pas % SOUS_CASES
    texte = chr(SOUS_CASES) * pleines
    if reste:
        texte += chr(reste)
    return texte + " " * (COLONNES - len(texte))


def splash_tick():
    """A appeler dans la boucle principale. True tant que l'animation dure."""
    global _splash, _splash_plein

    if not _splash:
        return False
    if _lcd is None:
        _splash = False
        return False

    t = time.monotonic() - _splash_t0

    # 1. apparition du titre, lettre par lettre
    if t < T_TITRE:
        _ecrire(0, _titre_partiel(t / T_LETTRE))
        return True

    _ecrire(0, _titre_partiel(len(TITRE)))

    if t < T_TITRE + T_PAUSE:
        return True

    # 2. remplissage
    avance = (t - T_TITRE - T_PAUSE) / T_BARRE

    if _splash_pret:
        pas = TOTAL
    elif avance < 1.0:
        pas = PALIER * avance
    else:
        # Le Pi n'a pas encore parle : la barre bat sur place plutot que
        # de pretendre avoir fini.
        pas = PALIER + 4 * abs(((t * 1.6) % 2.0) - 1.0)

    _ecrire(1, _barre_progression(pas), brut=True)

    # 3. sortie
    if _splash_pret:
        if _splash_plein == 0.0:
            _splash_plein = time.monotonic()
        elif time.monotonic() - _splash_plein >= T_FINAL:
            _splash = False
            _rendre()
            return False
    return True


def _fin_splash_immediate(rendre=True):
    """Coupe l'animation. rendre=False quand l'appelant redessine ensuite."""
    global _splash
    if _splash:
        _splash = False
        if rendre:
            _rendre()


# ---------------------------------------------------------------------------
# Rendu normal
# ---------------------------------------------------------------------------

def _rendre():
    if _splash:
        return
    if _mode_accordeur:
        _rendre_accordeur()
    else:
        _rendre_ligne1()
        _rendre_ligne2()


def _rendre_ligne1():
    nom = _propre(_nom_pedalboard)[:COLONNES - 1]
    nom += " " * (COLONNES - 1 - len(nom))
    _ecrire(0, nom + (" " if _lien_ok else "!"))


def _rendre_ligne2():
    if _index_snapshot is None:
        _ecrire(1, "")
        return
    _ecrire(1, "%d %s" % (_index_snapshot + 1, _nom_snapshot))


def _rendre_accordeur():
    if not _accordeur_dispo:
        _ecrire(0, "  Accordeur")
        _ecrire(1, "  absent du pdb")
        return

    if _note is None:
        _ecrire(0, "      --")
        _ecrire(1, "." * 7 + "||" + "." * 7)
        return

    gauche = _note.center(11)
    droite = "  OK " if abs(_cents) <= JUSTE else "%+4dc" % _cents
    _ecrire(0, gauche + droite)
    _ecrire(1, _barre(_cents))


def _barre(cents):
    """Barre de 16 cases. Repere central sur 7 et 8, marqueur mobile."""
    cases = ["."] * COLONNES
    cases[7] = "|"
    cases[8] = "|"

    c = max(-PLAGE, min(PLAGE, cents))
    pos = int(round(7.5 + c * 7.5 / PLAGE))
    pos = max(0, min(COLONNES - 1, pos))
    cases[pos] = "#"
    return "".join(cases)


# ---------------------------------------------------------------------------
# API appelee par retour_pipedal
# ---------------------------------------------------------------------------

def preset(nom):
    global _nom_pedalboard, _splash_pret
    if nom != _nom_pedalboard:
        _nom_pedalboard = nom
        if _splash:
            _splash_pret = True      # le Pi a parle : la barre peut finir
        elif not _mode_accordeur:
            _rendre_ligne1()


def snapshot(index, nom=None):
    """index en base 0. nom optionnel : conserve le precedent si absent."""
    global _index_snapshot, _nom_snapshot, _splash_pret
    change = False
    if index != _index_snapshot:
        _index_snapshot = index
        change = True
    if nom is not None and nom != _nom_snapshot:
        _nom_snapshot = nom
        change = True
    if not change:
        return
    if _splash:
        _splash_pret = True
    elif not _mode_accordeur:
        _rendre_ligne2()


def lien(ok):
    """Etat du lien avec le Pi. Affiche un '!' en bout de ligne 1."""
    global _lien_ok
    if ok != _lien_ok:
        _lien_ok = ok
        if not _splash and not _mode_accordeur:
            _rendre_ligne1()


def mode_accordeur(actif):
    global _mode_accordeur, _note, _accordeur_dispo
    if actif == _mode_accordeur:
        return
    _fin_splash_immediate(rendre=False)   # un appui au pied coupe l'animation
    _mode_accordeur = actif
    if actif:
        _note = None
        _accordeur_dispo = True
    _rendre()


def accordeur(note, cents, dispo=True):
    """note = None quand aucun signal n'est detecte."""
    global _note, _cents, _accordeur_dispo
    if (note, cents, dispo) == (_note, _cents, _accordeur_dispo):
        return
    _note = note
    _cents = cents
    _accordeur_dispo = dispo
    if _mode_accordeur and not _splash:
        _rendre_accordeur()
