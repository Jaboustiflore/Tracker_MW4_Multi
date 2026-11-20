"""Apprend les polices du jeu à partir d'écrans dont on connaît les valeurs,
puis mesure honnêtement la précision : chaque champ est lu avec un modèle appris SANS lui.

Usage : python entrainer.py image_fin_de_match.png image_rapport_de_combat.png
(les valeurs attendues ci-dessous correspondent aux deux écrans de référence utilisés pour le prototype)
"""
import os
import sys

import cv2
from police import Police

ICI = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) < 3:
    sys.exit(__doc__)
VIC = cv2.imread(sys.argv[1])
RAP = cv2.imread(sys.argv[2])

Y0, PAS = 421, 26.6
def row(i):
    return Y0 + i * PAS + 2, Y0 + (i + 1) * PAS - 2

# ---- police des tableaux de fin de match (zéro barré) ----
tableau = []
G = {"niveau": (128.5, 150), "score": (330, 420), "elim": (430, 520), "temps": (530, 620)}
D = {"niveau": (715, 740), "score": (915, 1005), "elim": (1015, 1105), "temps": (1115, 1205)}
vg = {"niveau": [45, 55, 55, 50, 34], "score": [5295, 4945, 4545, 3625, 1695],
      "elim": [34, 25, 15, 32, 7], "temps": [53, 71, 141, 11, 42]}
vd = {"niveau": [40, 24, 19, 43, 64, 42], "score": [6090, 5905, 4640, 4090, 3690, 2245],
      "elim": [34, 31, 31, 25, 27, 11], "temps": [88, 112, 32, 33, 17, 31]}
for cols, vals in ((G, vg), (D, vd)):
    for k, (x1, x2) in cols.items():
        for i, v in enumerate(vals[k]):
            y1, y2 = row(i)
            tableau.append((VIC, (x1, y1, x2, y2), str(v), f"{k}{'G' if cols is G else 'D'}{i+1}"))

# ---- police dorée du Rapport de combat ----
rapport = [
    (RAP, (982, 146, 1060, 166), "16", "moy_elim"),
    (RAP, (788, 188, 860, 208), "56", "parties"),
    (RAP, (982, 188, 1060, 208), "330", "spm"),
    (RAP, (825, 258, 925, 292), "1.17", "ratio_vd"),
    (RAP, (803, 328, 880, 346), "28", "victoires"),
    (RAP, (880, 328, 945, 346), "24", "defaites"),
    (RAP, (1015, 258, 1120, 292), "0.96", "ratio_em"),
    (RAP, (1000, 328, 1065, 346), "938", "elim"),
    (RAP, (1065, 328, 1135, 346), "982", "morts"),
    (RAP, (835, 396, 915, 430), "17", "serie"),
    (RAP, (1035, 396, 1105, 430), "37", "record"),
    (RAP, (945, 485, 985, 509), "4", "dom"), (RAP, (1165, 485, 1200, 509), "0", "conf"),
    (RAP, (945, 535, 985, 559), "1", "interc"), (RAP, (1160, 535, 1200, 559), "17", "ps"),
    (RAP, (945, 585, 985, 609), "0", "infl"), (RAP, (1160, 585, 1200, 609), "6", "tdm"),
    (RAP, (110, 337, 160, 356), "368", "arme1"), (RAP, (325, 337, 375, 356), "298", "arme2"),
    (RAP, (540, 337, 590, 356), "203", "arme3"),
]


def evaluer(nom, canal, data):
    ok_total, n = 0, 0
    erreurs, rejets = [], []
    for j, (img, box, verite, lbl) in enumerate(data):
        p = Police(nom, canal)
        for k, (img2, box2, v2, _) in enumerate(data):
            if k != j:
                p.apprendre(img2, box2, v2)
        lu, dist = p.lire(img, box, decimal="." in verite)
        n += 1
        if lu == verite:
            ok_total += 1
        else:
            erreurs.append(f"{lbl}: attendu {verite}, lu {lu!r}")
    full = Police(nom, canal)
    for img, box, v, lbl in data:
        if not full.apprendre(img, box, v):
            rejets.append(lbl)
    manquants = [d for d, v in full.echantillons.items() if not v]
    print(f"[{nom}] {ok_total}/{n} champs exacts ({100*ok_total/n:.0f} %) en validation croisée")
    for e in erreurs:
        print("   ✗", e)
    if rejets:
        print("   découpage à revoir :", rejets)
    print("   chiffres appris :", {d: len(v) for d, v in full.echantillons.items()}, "manquants :", manquants)
    return full


t = evaluer("tableau", "gray", tableau)
r = evaluer("rapport", "max", rapport)
t.sauver(os.path.join(ICI, "police_tableau.json"))
r.sauver(os.path.join(ICI, "police_rapport.json"))
