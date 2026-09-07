# Crade Cortex — schéma de câblage

[English](WIRING.md) · **Français**

Établi d'après `code.py`. Toute modification d'affectation dans le code doit
être reportée ici, et inversement.

---

## 1. Brochage physique du Pico

Le Pico a 40 broches. La 1 est en haut à gauche, connecteur USB vers le haut.
La numérotation descend à gauche jusqu'à 20, puis remonte à droite de 21 à 40.

```
                    ┌───── USB ─────┐
      S1   GP0  ────┤ 1          40 ├──── VBUS  → LCD 2 et 15
      S2   GP1  ────┤ 2          39 │     VSYS
           GND      │ 3          38 ├──── GND   → rail de masse
      S3   GP2  ────┤ 4          37 │     3V3_EN
      S4   GP3  ────┤ 5          36 │     3V3 OUT   (ne pas utiliser)
    Prst-  GP4  ────┤ 6          35 │     ADC_VREF
    Prst+  GP5  ────┤ 7          34 │     GP28
           GND      │ 8          33 │     AGND
    Accord GP6  ────┤ 9          32 │     GP27
    Libre  GP7  ────┤ 10         31 │     GP26
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

**22 broches utilisées sur 26 disponibles.** Restent libres : `GP22`, `GP26`,
`GP27`, `GP28`.

> **Ne jamais alimenter le LCD depuis la broche 36 (3V3).** Il lui faut du 5 V,
> donc la broche 40 (VBUS). Un HD44780 en 3,3 V ne s'allume pas ou affiche
> n'importe quoi.

---

## 2. Table de correspondance

| GPIO | Broche physique | Fonction |
|---|---|---|
| `GP0` | 1 | Switch S1 |
| `GP1` | 2 | Switch S2 |
| `GP2` | 4 | Switch S3 |
| `GP3` | 5 | Switch S4 |
| `GP4` | 6 | Switch F1 — preset précédent |
| `GP5` | 7 | Switch F2 — preset suivant |
| `GP6` | 9 | Switch F3 — accordeur |
| `GP7` | 10 | Switch F4 — libre |
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
| — | 38 | GND — rail de masse |
| — | 40 | VBUS — 5 V vers le LCD |

LED 1 et 2 sont à gauche, LED 3 à 8 à droite : c'est un héritage du câblage
initial sur `GP8`/`GP9`. Les déplacer ne servirait qu'à l'esthétique du faisceau,
et obligerait à recâbler ce qui fonctionne déjà.

---

## 2 bis. Disposition sur la face

Deux rangées de quatre, de gauche à droite. Le rang avant est celui qu'on
utilise le plus : il doit être le plus proche du bord.

```
   arriere   [ Preset - ] [ Preset + ] [ Accordeur ] [ Libre ]
                 GP4          GP5          GP6         GP7
                 CC 110       CC 111       CC 112      CC 113

   avant     [    S1    ] [    S2    ] [    S3     ] [   S4   ]
                 GP0          GP1          GP2         GP3
                 CC 102       CC 103       CC 104      CC 105
```

**Les LED se placent au-dessus des switches, jamais en dessous.** Le pied masque
la zone basse pendant l'appui : une LED sous le switch n'est visible qu'une fois
le pied retiré, c'est-à-dire trop tard.

**Au moins 25 mm entre les axes des deux rangées**, 40 mm si la place le permet.
En dessous, le talon accroche le rang arrière quand on appuie sur le rang avant.

Le boîtier passe de 27 mm à l'avant à 63 mm à l'arrière. Le rang arrière tombe
donc sur une zone plus épaisse et plus inclinée : vérifie qu'il reste assez de
hauteur sous la face pour le corps du footswitch et ses cosses, souvent 25 à
30 mm avec le fil.

### Bindings PiPedal correspondants

| Symbole système | CC |
|---|---|
| `snapshot1` … `snapshot4` | 102 … 105 |
| `prevProgram` | 110 |
| `nextProgram` | 111 |

Optionnel : lier le CC 112 au contrôle `MUTE` du TooB Tuner, pour couper le son
et afficher l'accordeur d'un seul geste.

---

## 3. Le rail de masse

Dix-neuf connexions vont à la masse : huit switches, huit LED, trois broches du
LCD. Les souder toutes sur la broche 38 est impossible.

**Fabrique un rail.** Un fil de cuivre nu, ou une piste de plaque à trous,
courant sur toute la longueur du montage. Une seule liaison le relie à la
broche 38 du Pico. Chaque masse individuelle vient s'y souder à l'endroit le plus
proche.

```
   broche 38 ────┬──────┬──────┬──────┬──────┬──────┬─────
                 │      │      │      │      │      │
              LCD 1   LED1   LED2    S1     S2    LED3  …
              LCD 5
              LCD 16
```

**Ce qu'il faut éviter, c'est le chaînage** — LED1 vers LED2 vers LED3 vers le
Pico. Électriquement ça marcherait à 50 mA, mais un faux contact au milieu de la
chaîne fait tomber tout ce qui est derrière, et tu passes la soirée à chercher.

Le rail donne un point de défaillance unique et identifiable au lieu de dix-neuf
points en série.

---

## 4. Les switches

Aucune résistance. Le pull-up interne du Pico est activé par le code
(`digitalio.Pull.UP`), les switches sont actifs à l'état bas.

```
   GPx ────────────○ ○──────────── rail de masse
                switch
```

| Switch | Vers |
|---|---|
| S1 | broche 1 et masse |
| S2 | broche 2 et masse |
| S3 | broche 4 et masse |
| S4 | broche 5 et masse |
| F1 — preset − | broche 6 et masse |
| F2 — preset + | broche 7 et masse |
| F3 — accordeur | broche 9 et masse |
| F4 — libre | broche 10 et masse |

Les footswitches à trois cosses sont souvent des inverseurs : utilise la cosse
commune et l'une des deux autres. Vérifie au multimètre quelle paire se ferme à
l'appui.

**Laisse le fil arriver détendu sur la cosse.** C'est elle qui encaisse la
contrainte mécanique de l'appui, transmise par le corps du switch. Un fil tendu
sur une soudure finit par lâcher, bien avant que le fil lui-même ne fatigue.

---

## 5. Les LED

Une résistance **par LED**, jamais partagée : une résistance commune fait varier
la luminosité selon le nombre de LED allumées.

```
   GPx ─────[ 330 Ω ]─────▶|───── rail de masse
                        anode  cathode
```

La patte longue est l'anode, côté résistance. La patte courte, et le méplat sur
le boîtier, indiquent la cathode, côté masse.

| LED | Broche |
|---|---|
| LED 1 | 11 |
| LED 2 | 12 |
| LED 3 | 21 |
| LED 4 | 22 |
| LED 5 | 24 |
| LED 6 | 25 |
| LED 7 | 26 |
| LED 8 | 27 |

### Sur la valeur de résistance

Avec 330 Ω et une LED rouge, la sortie 3,3 V du Pico débite environ 4 mA de
crête. Le code applique en plus un PWM à 12 %, ce qui donne une luminosité
volontairement basse.

Si c'est trop sombre sur scène, deux leviers dans cet ordre : **monte
`BRILLANCE`** dans `code.py`, c'est gratuit et réversible. Ensuite seulement,
descends à 220 Ω. Ne va pas sous 150 Ω : une broche du Pico est limitée à 12 mA.

> **Les LED bleues et blanches sont un cas à part.** Leur tension de seuil est de
> 3,0 à 3,2 V, soit presque le 3,3 V du Pico. Elles seront très sombres quelle
> que soit la résistance. Reste sur du rouge, du jaune ou du vert classique.

---

## 6. Le LCD1602

| Broche LCD | Vers |
|---|---|
| 1 VSS | rail de masse |
| 2 VDD | broche 40 — VBUS, 5 V |
| 3 V0 | curseur du potentiomètre |
| 4 RS | broche 14 |
| 5 R/W | **rail de masse** |
| 6 E | broche 15 |
| 7–10 D0–D3 | **rien**, mode 4 bits |
| 11 D4 | broche 16 |
| 12 D5 | broche 17 |
| 13 D6 | broche 19 |
| 14 D7 | broche 20 |
| 15 A | broche 40 — VBUS |
| 16 K | rail de masse |

### Potentiomètre de contraste

10 kΩ, trois pattes. Celle du **milieu** est le curseur.

```
   VBUS ──────┤ │ │├────── rail de masse
               └─┬─┘
                 └──────── LCD broche 3
```

Les deux extérieures sont interchangeables : les inverser inverse seulement le
sens de rotation.

**Sans lui, l'écran est soit tout noir, soit tout vide.** C'est la première cause
de « mon LCD ne marche pas ».

### Trois points qui comptent

**R/W impérativement à la masse.** Le LCD passe en écriture seule et ne peut plus
renvoyer du 5 V vers une entrée du Pico. C'est ce qui rend le mélange 5 V / 3,3 V
sans danger sur ce montage.

**Pas de résistance sur la broche 15.** Le module QAPASS 1602A porte déjà R8,
marquée `101`, soit 100 Ω, au dos près de la broche K. Sur un autre modèle,
vérifie avant de brancher — sinon 220 Ω en série.

**Ponte sur place.** Les broches 1, 5 et 16 vont toutes à la masse : relie-les
entre elles directement sur le LCD, un seul fil en sort. Pareil pour 2 et 15 vers
le VBUS. Tu passes de dix fils à huit, et le potentiomètre se monte à cheval sur
les broches 1, 2 et 3 sans fil volant.

---

## 7. Le Pico sur la plaque

Ne soude pas les fils directement sur le Pico. Soude **deux barrettes femelles
sur la plaque à trous**, et enfiche le Pico dedans. Tout le câblage arrive sur la
plaque, jamais sur la carte.

Le jour où tu veux remplacer le Pico, corriger une affectation ou le récupérer
pour autre chose, tu le retires d'un geste. Vingt fils soudés sur des pastilles
serrées, c'est une heure de dessoudage et une pastille arrachée.

Les barrettes coûtent 8 mm de hauteur. Si ton boîtier est serré à l'avant — 27 mm
seulement — souder le Pico à plat sur la plaque reste un compromis acceptable :
la plaque, elle, demeure modifiable.

**Soude les barrettes avec le Pico enfiché dedans.** Ça les maintient d'équerre.
À main levée elles partent de travers et n'entrent plus nulle part.

---

## 8. Ordre de montage

Chaque étape se teste avant de passer à la suivante.

1. **Le rail de masse et la liaison vers la broche 38.** Vérifie la continuité au
   multimètre entre les deux extrémités du rail.
2. **Le VBUS.** Contrôle l'absence de continuité entre le rail de masse et le
   5 V — un court ici empêcherait le Pico de démarrer.
3. **Le LCD**, potentiomètre compris. Au branchement, des rectangles noirs
   doivent apparaître : c'est la preuve qu'il est alimenté et vivant. Tourne le
   potentiomètre jusqu'à ce qu'ils s'estompent.
4. **Les LED, une par une.** Teste chacune avec
   `printf 'S1\n' > /dev/pipedal-pico` et ses variantes.
5. **Les switches, un par un.** `aseqdump -p XX:0` sur le Pi montre les CC qui
   partent.

---

## 9. Vérifications au multimètre

Pico débranché, avant la première mise sous tension :

| Test | Attendu |
|---|---|
| Rail de masse ↔ broche 38 | continuité |
| Broche 38 ↔ broche 40 | **pas** de continuité |
| Chaque cathode de LED ↔ rail | continuité |
| Chaque anode de LED ↔ sa broche | ~330 Ω |
| LCD 1, 5, 16 ↔ rail | continuité |
| LCD 2, 15 ↔ broche 40 | continuité |
| Deux broches GPIO voisines | **pas** de continuité |

Le dernier test attrape les ponts de soudure, qui sont la panne la plus courante
et la plus difficile à voir à l'œil nu sur une plaque à trous.

---

## 10. Récapitulatif des fils

| Destination | Fils vers la plaque |
|---|---|
| 8 switches | 8 signaux + 8 masses |
| 8 LED | 8 signaux + 8 masses |
| LCD | 6 signaux + 1 masse + 1 alim |
| Potentiomètre | 3 |
| **Total** | **42** |

Le fil monobrin de câble Cat 6 (23 AWG, 0,26 mm²) convient parfaitement : il
encaisse plusieurs ampères là où le montage en consomme 50 mA, il tient dans une
breadboard, son isolant supporte le fer, et les huit couleurs facilitent le
repérage.

Fixe une convention et note-la — masse en marron, 5 V en orange, par exemple.
Dans six mois, en rouvrant le boîtier, tu seras content de ne pas avoir à sonner
chaque fil.
