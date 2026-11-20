"""Reconnaît les écrans utiles de Call of Duty MW4 sur une image de l'écran.

Écrans reconnus :
  fin_match         écran VICTOIRE / DÉFAITE avec les tableaux des deux équipes
  parties_recentes  Carrière > Rapport de combat > Parties récentes (10 dernières parties)
  rapport_combat    Carrière > Rapport de combat (stats depuis le début)
  carriere          page Carrière (niveau, prestige)
  rapport_bataille  « Rapport de bataille » affiché après un match (carte, score, élim., temps obj.)

Méthode : comparaison avec des modèles découpés dans de vraies captures du jeu (dossier modeles/).
Pour la fin de match, on cherche la couleur du texte de l'en-tête des tableaux (cyan ou rouge),
ce qui ne dépend pas du décor derrière, plus le bandeau du joueur en bas de l'écran.
Le tableau Tab affiché en cours de partie ne déclenche pas : son en-tête est beaucoup plus haut.

Tout se fait sur une copie de l'image en 1280x720 : ça marche en 1080p, 1440p ou 4K.
"""
import os
import sys

import cv2
import numpy as np

ICI = os.path.dirname(os.path.abspath(__file__))
# dans la version .exe, les modèles sont décompressés dans sys._MEIPASS
DOSSIER_MODELES = os.path.join(getattr(sys, "_MEIPASS", ICI), "modeles")

# zones de recherche (x1, y1, x2, y2) sur l'image ramenée en 1280x720
ZONES = {
    "entete": (20, 360, 1260, 460),
    "bandeau": (520, 590, 760, 680),
    "rapport_titre": (20, 0, 460, 110),
    "parties_titre": (10, 0, 480, 110),
    "carriere_titre": (20, 0, 380, 110),
    "bataille_titre": (20, 0, 460, 110),
}
SEUILS = {"entete": 0.60, "bandeau": 0.80, "titre": 0.75}


def _charger(nom):
    img = cv2.imread(os.path.join(DOSSIER_MODELES, nom), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Modèle manquant : modeles/{nom}")
    return img


ECHELLES = (0.85, 0.88, 0.91, 0.94, 0.97, 1.0, 1.03, 1.06, 1.09, 1.12, 1.15)   # tolère d'autres résolutions et l'échelle de l'interface


def _echelles(img):
    return [cv2.resize(img, None, fx=e, fy=e, interpolation=cv2.INTER_AREA if e < 1 else cv2.INTER_LINEAR) for e in ECHELLES]


MODELES = {k: _echelles(_charger(f)) for k, f in {
    "entete_cyan": "fin_entete_cyan.png",
    "entete_rouge": "fin_entete_rouge.png",
    "bandeau": "fin_bandeau.png",
    "rapport_titre": "rapport_titre.png",
    "parties_titre": "parties_titre.png",
    "carriere_titre": "carriere_titre.png",
    "bataille_titre": "bataille_titre.png",
    "mot_combat": "mot_combat.png",
    "mot_bataille": "mot_bataille.png",
}.items()}
# l'en-tête de l'écran de défaite (capturé en vrai en 1080p) complète celui de la victoire
MODELES["entete_cyan"] += _echelles(_charger("fin_entete_cyan_defaite.png"))


def en_720p(img):
    """Recadre au centre en 16:9 (écrans 21:9 ou 16:10) puis ramène en 1280x720."""
    h, w = img.shape[:2]
    r = w / h
    if r > 16 / 9 + 0.02:
        nw = int(h * 16 / 9)
        x = (w - nw) // 2
        img = img[:, x:x + nw]
    elif r < 16 / 9 - 0.02:
        nh = int(w * 9 / 16)
        y = (h - nh) // 2
        img = img[y:y + nh]
    return cv2.resize(img, (1280, 720), interpolation=cv2.INTER_AREA)


def _zone(img, nom):
    x1, y1, x2, y2 = ZONES[nom]
    return img[y1:y2, x1:x2]


def _score(zone, modeles):
    if not zone.any():
        return 0.0
    best = 0.0
    for m in modeles:
        if zone.shape[0] < m.shape[0] or zone.shape[1] < m.shape[1]:
            continue
        best = max(best, float(cv2.matchTemplate(zone, m, cv2.TM_CCOEFF_NORMED).max()))
    return best


def scores(img720):
    hsv = cv2.cvtColor(_zone(img720, "entete"), cv2.COLOR_BGR2HSV)
    cyan = cv2.inRange(hsv, (78, 70, 110), (102, 255, 255))
    rouge = cv2.inRange(hsv, (0, 90, 110), (10, 255, 255)) | cv2.inRange(hsv, (170, 90, 110), (180, 255, 255))
    gris = cv2.cvtColor(img720, cv2.COLOR_BGR2GRAY)
    return {
        "entete": max(_score(cyan, MODELES["entete_cyan"]), _score(rouge, MODELES["entete_rouge"])),
        "bandeau": _score(_zone(gris, "bandeau"), MODELES["bandeau"]),
        "rapport_titre": _score(_zone(gris, "rapport_titre"), MODELES["rapport_titre"]),
        "parties_titre": _score(_zone(gris, "parties_titre"), MODELES["parties_titre"]),
        "carriere_titre": _score(_zone(gris, "carriere_titre"), MODELES["carriere_titre"]),
        "bataille_titre": _score(_zone(gris, "bataille_titre"), MODELES["bataille_titre"]),
    }


def detecter(img):
    """Renvoie (type d'écran ou None, scores). img : image BGR de l'écran, n'importe quelle taille."""
    s = scores(en_720p(img))
    if s["entete"] >= SEUILS["entete"] and s["bandeau"] >= SEUILS["bandeau"]:
        return "fin_match", s
    if s["rapport_titre"] >= SEUILS["titre"] or s["bataille_titre"] >= SEUILS["titre"]:
        # « RAPPORT DE COMBAT » et « RAPPORT DE BATAILLE » : on départage sur le dernier mot
        g = cv2.cvtColor(en_720p(img), cv2.COLOR_BGR2GRAY)[0:110, 120:520]
        mc, mb = _score(g, MODELES["mot_combat"]), _score(g, MODELES["mot_bataille"])
        s["mot_combat"], s["mot_bataille"] = mc, mb
        if max(mc, mb) >= 0.7:
            return ("rapport_combat" if mc > mb else "rapport_bataille"), s
    titres = [("parties_recentes", s["parties_titre"]), ("rapport_combat", s["rapport_titre"]),
              ("carriere", s["carriere_titre"]), ("rapport_bataille", s["bataille_titre"])]
    nom, best = max(titres, key=lambda x: x[1])
    if best >= SEUILS["titre"]:
        return nom, s
    return None, s


def empreinte(img, zone=None):
    """Vignette grise de la zone, pour savoir si son contenu a changé (ex. autre partie sélectionnée)."""
    im = en_720p(img)
    if zone:
        x1, y1, x2, y2 = zone
        im = im[y1:y2, x1:x2]
    return cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.int16)


def difference(a, b):
    """Part des pixels qui ont franchement changé (0 = identique, 1 = tout a changé). Insensible au bruit léger."""
    if a is None or b is None or a.shape != b.shape:
        return 1.0
    return float((np.abs(a - b) > 30).mean())
