"""Prototype : lit un écran de Call of Duty MW4 (capture ou image de vidéo) et en sort les stats en JSON.

Écrans reconnus :
  - fin de match multijoueur (VICTOIRE / DÉFAITE + tableau des deux équipes)
  - Carrière > Rapport de combat > Multijoueur (stats globales du joueur)

Méthode :
  - chiffres : reconnus avec les polices exactes du jeu (police.py, modèles appris sur de vrais écrans)
  - textes (pseudos, mode, résultat) : OCR Tesseract
  - contrôles de cohérence (ratio = élim / morts, etc.) pour repérer toute lecture douteuse
Les zones sont en coordonnées relatives (mesurées sur 1280x720), donc valables en 720p, 1080p, 1440p.

Usage : python lecteur_cod.py image.png [image2.png ...]
"""
import json
import os
import re
import sys

import cv2
import pytesseract

from police import Police, binariser, glyphes, zone

ICI = os.path.dirname(os.path.abspath(__file__))
POLICES = os.path.join(ICI, "polices_apprises.json")
P_TABLEAU = Police("tableau", "gray").charger_echantillons(POLICES, "tableau")
P_RAPPORT = Police("rapport", "max").charger_echantillons(POLICES, "rapport")
P_BARRE = Police("barre", "gray").charger_echantillons(POLICES, "rapport")


def texte(img, box, psm=7, lang="fra+eng"):
    b = binariser(zone(img, *box), "gray")
    b = cv2.copyMakeBorder(cv2.bitwise_not(b), 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    return " ".join(pytesseract.image_to_string(b, lang=lang, config=f"--psm {psm}").split())


def pseudo(img, box):
    t = texte(img, box, lang="eng")
    if len(re.findall(r"[A-Za-z0-9]", t)) < 2:          # pseudo non latin (coréen, etc.)
        t = texte(img, box, lang="kor+jpn+chi_sim")
    t = re.sub(r"^[^\w\[]+", "", t)          # débris d'icône avant le pseudo
    t = re.sub(r"[^\w\]]+$", "", t)          # ponctuation parasite après
    # tags de clan : « HRT ]Amya » → « [HRT]Amya », « [TIMPJOuais » → « [TIMP]Ouais »
    t = re.sub(r"^\[?([A-Z0-9]{2,6})\s*\]\s*", r"[\1]", t)
    if t.startswith("[") and "]" not in t:
        t = re.sub(r"^\[([A-Z0-9]{2,6})J", r"[\1]", t)
    return t


def nombre(police, img, box, decimal=False):
    t, _ = police.lire(img, box, decimal=decimal)
    if not t:
        return None
    try:
        return float(t) if decimal else int(t)
    except ValueError:
        return None


def ligne_vide(img, box):
    """Vide s'il n'y a aucun chiffre dans la colonne Score de la ligne."""
    gl, _ = glyphes(zone(img, *box), "gray")
    return sum(1 for t, _ in gl if t == "chiffre") < 2


def ligne_surlignee(img, box):
    hsv = cv2.cvtColor(zone(img, *box), cv2.COLOR_BGR2HSV)
    return bool(cv2.inRange(hsv, (15, 80, 80), (40, 255, 255)).mean() / 255 > 0.04)


def type_ecran(img):
    haut = texte(img, (40, 10, 700, 120), psm=6).upper()
    if "RAPPORT DE COMBAT" in haut or "CARRI" in haut:
        return "rapport_combat"
    if "VICTOIRE" in haut or "FAITE" in haut:
        return "fin_match"
    return "inconnu"


# ---------- fin de match ----------
Y0, PAS = 421, 26.6
COLS = {
    "equipe": {"niveau": (128.5, 150), "joueur": (168, 325), "score": (330, 420), "elim": (430, 520),
               "temps_obj": (530, 620), "ligne": (65, 625)},
    "adversaires": {"niveau": (715, 740), "joueur": (752, 910), "score": (915, 1005), "elim": (1015, 1105),
                    "temps_obj": (1115, 1205), "ligne": (650, 1212)},
}


def lire_equipe(img, c):
    joueurs = []
    for i in range(6):
        y1, y2 = Y0 + i * PAS + 2, Y0 + (i + 1) * PAS - 2
        if ligne_vide(img, (c["score"][0], y1, c["score"][1], y2)):
            continue
        joueurs.append({
            "rang": i + 1,
            "joueur": pseudo(img, (c["joueur"][0], y1, c["joueur"][1], y2)),
            "niveau": nombre(P_TABLEAU, img, (c["niveau"][0], y1, c["niveau"][1], y2)),
            "score": nombre(P_TABLEAU, img, (c["score"][0], y1, c["score"][1], y2)),
            "elim": nombre(P_TABLEAU, img, (c["elim"][0], y1, c["elim"][1], y2)),
            "temps_obj": nombre(P_TABLEAU, img, (c["temps_obj"][0], y1, c["temps_obj"][1], y2)),
            "moi": ligne_surlignee(img, (c["ligne"][0], y1 + 3, c["ligne"][1], y2 - 3)),
        })
    return joueurs


def lire_fin_match(img):
    titre = texte(img, (50, 35, 320, 118)).upper()
    return {
        "ecran": "fin_match",
        "resultat": "victoire" if "VICTOIRE" in titre else ("defaite" if "FAITE" in titre else titre.lower()),
        "mode": texte(img, (60, 130, 260, 156)),
        "score_equipe": None,    # gros chiffres stylisés : police à apprendre (pas assez d'exemples)
        "score_adverse": None,
        "equipe": lire_equipe(img, COLS["equipe"]),
        "adversaires": lire_equipe(img, COLS["adversaires"]),
        "moi": {
            "joueur": pseudo(img, (372, 622, 520, 642)),
            "niveau": nombre(P_BARRE, img, (340, 657, 362, 673)),
            "elim_assist": nombre(P_BARRE, img, (600, 645, 670, 670)),
            "morts": nombre(P_BARRE, img, (740, 645, 810, 670)),
            "ratio": nombre(P_BARRE, img, (860, 645, 940, 670), decimal=True),
        },
    }


# ---------- rapport de combat ----------
RC = {
    "moy_elim_partie": (982, 146, 1060, 166), "parties_jouees": (788, 188, 860, 208),
    "score_par_minute": (982, 188, 1060, 208), "victoires": (803, 328, 880, 346),
    "defaites": (880, 328, 945, 346), "elim": (1000, 328, 1065, 346), "morts": (1065, 328, 1135, 346),
    "meilleure_serie": (835, 396, 915, 430), "record_elim_partie": (1035, 396, 1105, 430),
}
RC_DEC = {"ratio_vd": (825, 258, 925, 292), "ratio_em": (1015, 258, 1120, 292)}
MODES_RC = {
    "domination": (945, 485, 985, 509), "elimination_confirmee": (1165, 485, 1200, 509),
    "interception": (945, 535, 985, 559), "point_strategique": (1160, 535, 1200, 559),
    "inflation": (945, 585, 985, 609), "match_a_mort_equipe": (1160, 585, 1200, 609),
}


def lire_rapport(img):
    out = {"ecran": "rapport_combat", "section": texte(img, (780, 88, 1000, 122)),
           "temps_de_jeu": texte(img, (788, 146, 905, 166), lang="eng")}
    for k, b in RC.items():
        out[k] = nombre(P_RAPPORT, img, b)
    for k, b in RC_DEC.items():
        out[k] = nombre(P_RAPPORT, img, b, decimal=True)
    out["victoires_par_mode"] = {k: nombre(P_RAPPORT, img, b) for k, b in MODES_RC.items()}
    return out


def proche(a, b, tol=0.011):
    return a is not None and b is not None and abs(a - b) <= tol


def verifier(r):
    """Contrôles de cohérence : un chiffre mal lu se voit tout de suite."""
    alertes = []
    if r["ecran"] == "rapport_combat":
        if r["victoires"] and r["defaites"] and not proche(r["victoires"] / r["defaites"], r["ratio_vd"]):
            alertes.append("ratio V/D ≠ victoires / défaites")
        if r["elim"] and r["morts"] and not proche(r["elim"] / r["morts"], r["ratio_em"]):
            alertes.append("ratio É/M ≠ élim / morts")
        if r["elim"] and r["parties_jouees"] and r["moy_elim_partie"] is not None:
            if int(r["elim"] / r["parties_jouees"]) != r["moy_elim_partie"]:
                alertes.append("moyenne élim/partie ≠ élim / parties")
    if r["ecran"] == "fin_match":
        m = r["moi"]
        if m["elim_assist"] is not None and m["morts"]:
            if not proche(m["elim_assist"] / m["morts"], m["ratio"]):
                alertes.append("ratio de fin de match ≠ élim / morts")
        lignes = [p for p in r["equipe"] + r["adversaires"] if p["moi"]]
        if not lignes:
            alertes.append("ligne du joueur introuvable dans le tableau")
        else:
            ma_ligne = lignes[0]
            if m["joueur"] and ma_ligne["joueur"] != m["joueur"]:
                alertes.append("pseudo de la ligne surlignée ≠ pseudo du bandeau")
            if m.get("niveau") and ma_ligne["niveau"] != m["niveau"]:
                # le bandeau est plus lisible que la ligne jaune : on corrige et on le note
                r.setdefault("corrections", []).append(
                    f"niveau de la ligne surlignée corrigé {ma_ligne['niveau']} → {m['niveau']} (lu dans le bandeau)")
                ma_ligne["niveau"] = m["niveau"]
    r["alertes"] = alertes
    r["fiable"] = not alertes
    return r


def lire(path):
    img = cv2.imread(path)
    if img is None:
        return {"ecran": "illisible", "fichier": path}
    t = type_ecran(img)
    if t == "fin_match":
        return verifier(lire_fin_match(img))
    if t == "rapport_combat":
        return verifier(lire_rapport(img))
    return {"ecran": "inconnu", "fichier": path}


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(json.dumps(lire(p), ensure_ascii=False, indent=2))
