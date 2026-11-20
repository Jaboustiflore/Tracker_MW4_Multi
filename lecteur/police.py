"""Reconnaissance des chiffres avec les polices exactes du jeu (comparaison de modèles).

L'OCR générique confond le zéro barré du jeu avec 8/9/6. Ici, on apprend chaque chiffre
à partir d'écrans dont on connaît les valeurs, puis on reconnaît par ressemblance.
Les glyphes sont normalisés (16x24), donc ça marche quelle que soit la résolution.
"""
import json
import cv2
import numpy as np

GW, GH = 16, 24
W0, H0 = 1280, 720


def zone(img, x1, y1, x2, y2):
    h, w = img.shape[:2]
    return img[int(y1 / H0 * h):int(y2 / H0 * h), int(x1 / W0 * w):int(x2 / W0 * w)]


def binariser(crop, canal):
    if canal == "min":      # texte blanc/gris (tableaux), insensible au fond coloré
        g = crop.min(axis=2)
    elif canal == "max":    # texte doré (Rapport de combat)
        g = crop.max(axis=2)
    else:
        g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    g = cv2.resize(g, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    _, b = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if b.mean() > 127:  # fond plus clair que le texte (ligne surlignée) : on inverse
        b = cv2.bitwise_not(b)
    return b


def glyphes(crop, canal):
    """Découpe une zone en glyphes (chiffres et point décimal), de gauche à droite."""
    b = binariser(crop, canal)
    n, lab, st, _ = cv2.connectedComponentsWithStats(b, 8)
    comps = [tuple(s) for s in st[1:] if s[4] >= 6]
    # on ignore ce qui touche le bord gauche/droit (bouts d'icônes voisines)
    comps = [s for s in comps if s[0] > 1 and s[0] + s[2] < b.shape[1] - 1]
    if not comps:
        return [], b
    hmax = max(s[3] for s in comps)
    grands = sorted([s for s in comps if s[3] >= 0.55 * hmax], key=lambda s: s[0])
    petits = [s for s in comps if s[3] < 0.55 * hmax]
    # regroupe les morceaux d'un même chiffre (ex. barre intérieure du zéro)
    groupes = []
    for s in grands:
        x, y, w, h, a = s
        if groupes:
            gx1, gy1, gx2, gy2 = groupes[-1]["box"]
            chevauche = min(gx2, x + w) - max(gx1, x)
            if chevauche > 0.5 * min(w, gx2 - gx1):
                groupes[-1]["box"] = (min(gx1, x), min(gy1, y), max(gx2, x + w), max(gy2, y + h))
                continue
        groupes.append({"box": (x, y, x + w, y + h), "type": "chiffre"})
    bas = max(g["box"][3] for g in groupes)
    for s in petits:
        x, y, w, h, a = s
        dans = [g for g in groupes if g["box"][0] - 1 <= x and x + w <= g["box"][2] + 1]
        if dans:
            g = dans[0]
            gx1, gy1, gx2, gy2 = g["box"]
            g["box"] = (gx1, min(gy1, y), gx2, max(gy2, y + h))
        elif y + h >= bas - 0.25 * hmax and h < 0.35 * hmax:
            groupes.append({"box": (x, y, x + w, y + h), "type": "point"})
    groupes.sort(key=lambda g: g["box"][0])
    out = []
    for g in groupes:
        x1, y1, x2, y2 = g["box"]
        if g["type"] == "point":
            out.append(("point", None))
            continue
        m = b[y1:y2, x1:x2]
        v = cv2.resize(m, (GW, GH), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        out.append(("chiffre", v))
    return out, b


class Police:
    def __init__(self, nom, canal):
        self.nom, self.canal = nom, canal
        self.echantillons = {str(d): [] for d in range(10)}

    def apprendre(self, img, box, texte):
        gl, _ = glyphes(zone(img, *box), self.canal)
        chiffres = [v for t, v in gl if t == "chiffre"]
        attendus = [c for c in texte if c.isdigit()]
        if len(chiffres) != len(attendus):
            return False
        for c, v in zip(attendus, chiffres):
            self.echantillons[c].append(v)
        return True

    def modeles(self):
        return {d: np.mean(v, axis=0) for d, v in self.echantillons.items() if v}

    def charger_echantillons(self, path, nom=None):
        d = json.load(open(path))
        if nom is not None:   # format compact (polices_apprises.json) : glyphe 16x24 en 96 caractères hexa
            for c, exs in d[nom]["glyphes"].items():
                self.echantillons[c] = [np.array(list(f"{int(h, 16):0384b}"), dtype=np.float32).reshape(GH, GW)
                                        for h in exs]
            return self
        for c, exs in d["echantillons"].items():
            self.echantillons[c] = [np.array(e, dtype=np.float32) for e in exs]
        return self

    def lire(self, img, box, decimal=False):
        gl, _ = glyphes(zone(img, *box), self.canal)
        txt, scores = "", []
        for t, v in gl:
            if t == "point":
                if decimal:
                    txt += "."
                continue
            # exemple le plus proche (1-NN), plus fiable que la moyenne avec peu d'exemples
            best_d, best_c = None, None
            for c, exs in self.echantillons.items():
                for e in exs:
                    d = float(((e - v) ** 2).sum())
                    if best_d is None or d < best_d:
                        best_d, best_c = d, c
            if best_c is None:
                continue
            txt += best_c
            scores.append(best_d)
        return txt.strip("."), (max(scores) if scores else None)

    def sauver(self, path):
        json.dump({"nom": self.nom, "canal": self.canal,
                   "echantillons": {d: [e.round(3).tolist() for e in v] for d, v in self.echantillons.items()}},
                  open(path, "w"))
