# Protocole websocket de PiPedal

[English](PROTOCOL.md) · **Français**

Relevé par capture sur **PiPedal 2.0.110**, côté navigateur.

> **API interne, non documentée par le projet.** Elle changera d'une version à
> l'autre. Épingle-toi à une version connue et revérifie après chaque mise à
> jour. Rien de ce qui suit n'est un contrat.

**Endpoint :** `ws://<hôte>:80/pipedal`

Le port par défaut est 80 sur Raspberry Pi OS. Sous Ubuntu, PiPedal bascule
généralement sur le 81, Apache occupant le 80. `pipedalconfig` permet de le
changer.

---

## Enveloppe

Tableau JSON à un ou deux éléments : `[entête]` ou `[entête, corps]`.

```jsonc
// requête sans argument
[{"message": "hello", "replyTo": 2}]

// requête avec argument
[{"message": "monitorPort", "replyTo": 24},
 {"instanceId": 16, "key": "FREQ", "updateRate": 0.05}]

// réponse du serveur
[{"reply": 2, "message": "ehlo"}, 20]
```

Deux champs, jamais ensemble :

- **`replyTo`** — « réponds-moi avec cet identifiant ». Présent sur les requêtes
  du client, et sur les messages poussés par le serveur qui attendent un accusé.
- **`reply`** — « ceci est la réponse à cet identifiant ».

Ce n'est **pas** du JSON-RPC 2.0. L'implémentation est un proxy d'objet distant
écrit à la main, entre `PiPedalModel.tsx` côté client et `PiPedalModel.cpp` côté
serveur.

---

## Poignée de main

**Le client doit envoyer `hello` dès la connexion.**

```jsonc
[{"message": "hello", "replyTo": 2}]
[{"reply": 2, "message": "ehlo"}, 20]
```

Sans lui, le serveur accepte la connexion, répond aux requêtes, et **ne diffuse
jamais rien**. C'est un échec silencieux : tout semble fonctionner jusqu'à ce
qu'on remarque qu'aucun événement n'arrive.

---

## Accusés de réception

Quand l'entête d'un message poussé contient `replyTo`, le client doit répondre :

```jsonc
[{"replyTo": 996, "message": "onVuUpdate"}, { … }]
[{"reply": 996, "message": "onVuUpdate"}, true]
```

C'est du contrôle de flux : le serveur numérote, attend l'accusé, et n'envoie la
suite qu'après. Un client qui n'acquitte pas finit par ne plus rien recevoir.

`onPedalboardChanged` n'a pas de `replyTo` et ne demande donc rien.

---

## État du pedalboard

### Diffusion sur changement

Émise à **tous** les clients connectés, y compris celui qui a provoqué le
changement. C'est ce qui permet à un contrôleur physique de confirmer ses propres
actions.

```jsonc
[{"message": "onPedalboardChanged"},
 {"clientId": -1,
  "pedalboard": {
    "name": "Fender Clean",
    "selectedSnapshot": 1,        // BASE 0
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

Points à connaître :

- **`selectedSnapshot` est en base 0.**
- **`snapshots` contient des trous** (`null`) pour les emplacements vides. Ne pas
  supposer que l'index est valide.
- **Chaque diffusion pèse ~9 ko** : le pedalboard entier est renvoyé, pas
  seulement ce qui a changé. Relever `max_size` sur la connexion.
- **`isModified`** indique un snapshot édité mais non sauvegardé.
- **`color`** donne la couleur du snapshot telle qu'affichée dans l'UI.

### État initial

```jsonc
[{"message": "currentPedalboard", "replyTo": 8}]
```

La réponse place le pedalboard **à la racine du corps**, pas sous une clé
`pedalboard` comme dans la diffusion :

```jsonc
[{"reply": 8, "message": "currentPedalboard"},
 {"name": "Fender Clean", "selectedSnapshot": 0, "items": [ … ]}]
```

### Commande

```jsonc
[{"message": "setSnapshot"}, 0]
```

---

## Ports de monitoring

Permet de suivre en continu la valeur d'un port de sortie LV2.

```jsonc
[{"message": "monitorPort", "replyTo": 24},
 {"instanceId": 16, "key": "FREQ", "updateRate": 0.05}]

// la reponse porte le handle d'abonnement
[{"reply": 24, "message": "monitorPort"}, 29]

// puis, periodiquement
[{"replyTo": 2, "message": "onMonitorPortOutput"},
 {"subscriptionHandle": 29, "value": 40.12}]

// desabonnement
[{"message": "unmonitorPort"}, 29]
```

`updateRate` est une **période en secondes**, pas une fréquence. Le client web
utilise 0,0333 (30 Hz) et 0,0667 (15 Hz).

### Exemple : accordeur

Le plugin **TooB Tuner** (`http://two-play.com/plugins/toob-tuner`) expose un
port `FREQ` qui donne un **numéro de note MIDI flottant**, `-1` en l'absence de
signal.

```python
NOTES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

def note_et_cents(valeur):
    if valeur is None or valeur < 0:
        return (None, 0)
    entier = int(round(valeur))
    cents = int(round((valeur - entier) * 100))
    return (NOTES[entier % 12] + str(entier // 12 - 1), cents)
```

**Ne jamais coder l'`instanceId` en dur.** Elle change avec le pedalboard. La
retrouver dans `items` en cherchant l'URI du plugin, et se réabonner quand elle
bouge.

### Autres ports intéressants

Relevés dans le descripteur `plugins` :

| Plugin | Port de sortie | Contenu |
|---|---|---|
| TooB Neural Amp Modeler | `gateOut` | État du noise gate, 0 ou 1 |
| TooB NAM | `inputGainOut` | Niveau d'entrée en dB |
| Gxdigital_delay | `DD_NOTIFY` | Tempo en BPM |
| TooB 4Looper | `position1` | Position dans la boucle, 0 à 1 |
| TooB 4Looper | `record_led1`, `play_led1` | État d'enregistrement et lecture |
| TooB 4Looper | `bar_led`, `beat_led` | Mesures et temps |
| TooB File Player | `position`, `duration`, `state` | Lecture de fichier |

---

## VU-mètres

```jsonc
[{"message": "addVuSubscription", "replyTo": 23}, 16]
[{"reply": 23, "message": "addVuSubscription"}, 28]

[{"replyTo": 996, "message": "onVuUpdate"},
 {"instanceId": 16, "sampleTime": 2741501184,
  "isStereoInput": false, "isStereoOutput": false,
  "inputMaxValueL": 6.55e-05, "inputMaxValueR": 0,
  "outputMaxValueL": 6.55e-05, "outputMaxValueR": 0}]
```

Ces messages **exigent un accusé**. Le flux est nourri : ne s'y abonner qu'en cas
de besoin réel.

---

## Bindings MIDI système

```jsonc
[{"message": "getSystemMidiBindings", "replyTo": 22}]
```

Les symboles disponibles :

```
prevBank      nextBank
prevProgram   nextProgram
snapshot1 … snapshot6
prevSnapshot  nextSnapshot
startHotspot  stopHotspot
shutdown      reboot
```

`shutdown` et `reboot` permettent d'arrêter proprement le Raspberry Pi depuis un
footswitch. Ce n'est pas anecdotique : couper l'alimentation sans arrêt propre
peut faire perdre presets, banques et configuration.

Structure d'un binding :

```jsonc
{"channel": -1, "symbol": "snapshot1", "bindingType": 2,
 "note": 72, "control": 102,
 "minControlValue": 0, "maxControlValue": 127,
 "minValue": 0, "maxValue": 1,
 "rotaryScale": 1, "linearControlType": 0, "switchControlType": 0}
```

`bindingType` vaut 0 quand le binding est inactif, 2 pour un contrôle MIDI CC.

---

## Autres messages observés

| Message | Contenu |
|---|---|
| `version` | Version serveur, OS, adresses web |
| `plugins` | Descripteur complet de tous les plugins LV2 — volumineux |
| `pluginClasses` | Taxonomie des types de plugins |
| `getPresets` | Liste des presets avec `instanceId` et nom |
| `getBankIndex` | Banques disponibles et banque sélectionnée |
| `getJackConfiguration` | Fréquence, taille de buffer, ports audio et MIDI |
| `getJackServerSettings` | Périphérique ALSA, buffers |
| `getUpdateStatus` | Mise à jour disponible |
| `getShowStatusMonitor` | Affichage du moniteur système |
| `imageList` | Ressources graphiques de l'UI |
| `getFavorites`, `getWifiConfigSettings`, `getGovernorSettings` | Configuration |

---

## Séquence d'ouverture du client web

Pour référence, l'ordre observé au chargement de la page :

```
getWifiRegulatoryDomains → hello → imageList → version → getUpdateStatus
→ getHasWifi → plugins → currentPedalboard → pluginClasses → getPresets
→ getWifiConfigSettings → … → getSystemMidiBindings
→ addVuSubscription → monitorPort ×4
```

Un client minimal n'a besoin que de `hello` puis `currentPedalboard`.

---

## Implémentation de référence

`pi/pipedal_bridge.py` dans ce dépôt : environ 400 lignes, avec reconnexion,
accusés, abonnement conditionnel et limitation de débit.
