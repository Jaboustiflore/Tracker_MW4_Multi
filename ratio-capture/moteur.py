"""Décide quand enregistrer une capture : une seule par écran de fin de match,
une par partie consultée dans « Parties récentes », une par visite du Rapport de combat ou de la Carrière."""
import os
import time

import cv2

from detecteur import detecter, difference, empreinte

PANNEAU_DETAIL = (565, 115, 1230, 705)  # partie droite de « Parties récentes » (détail de la partie sélectionnée)
# zone qui porte les chiffres de chaque page : on ne recapture une page revisitée que si elle a changé
ZONE_CONTENU = {
    "rapport_combat": (760, 90, 1260, 700),
    "carriere": (60, 80, 400, 660),
    "rapport_bataille": (60, 80, 680, 600),
}


class Capteur:
    def __init__(self, dossier, delai_stable=1.0, oubli=2.5, max_par_ecran=12):
        self.dossier = dossier
        self.delai_stable = delai_stable    # l'écran doit être là depuis 1 s (fin des animations)
        self.oubli = oubli                  # absence tolérée avant de considérer que l'écran est parti
        self.max_par_ecran = max_par_ecran
        self.courant = None
        self.depuis = 0.0
        self.vu_le = 0.0
        self.capture_faite = False
        self.empr_capt = None
        self.empr_prec = None
        self.instable_depuis = None
        self.n = 0
        self.noir_depuis = None
        self.deja_vu = {}   # dernière empreinte enregistrée par type de page

    def _nouvel_ecran(self, typ, t):
        self.courant, self.depuis, self.capture_faite = typ, t, False
        self.empr_capt = self.empr_prec = None
        self.instable_depuis = None
        self.n = 0

    def ecran_noir(self, img, t):
        """Vrai si l'image capturée est noire depuis plus de 10 s (plein écran exclusif non capturable)."""
        if img is None or img.mean() < 3:
            if self.noir_depuis is None:
                self.noir_depuis = t
            return t - self.noir_depuis > 10
        self.noir_depuis = None
        return False

    def traiter(self, img, t=None):
        """img : image BGR de l'écran en pleine résolution. Renvoie (type détecté, chemin enregistré ou None)."""
        t = time.monotonic() if t is None else t
        typ, _ = detecter(img)
        if typ is None:
            if self.courant and t - self.vu_le > self.oubli:
                self.courant = None
            return None, None
        if typ != self.courant:
            self._nouvel_ecran(typ, t)
        self.vu_le = t
        if t - self.depuis < self.delai_stable:
            return typ, None
        if typ == "parties_recentes":
            e = empreinte(img, PANNEAU_DETAIL)
            bouge = difference(e, self.empr_prec)
            stable = bouge < 0.0005                              # le panneau ne bouge plus
            if not stable and self.instable_depuis is None:
                self.instable_depuis = t
            if stable:
                self.instable_depuis = None
            longtemps = self.instable_depuis is not None and t - self.instable_depuis > 3   # fond animé : on n'attend pas indéfiniment
            nouveau = difference(e, self.empr_capt) > (0.0008 if stable else 0.02)    # autre chose que la dernière capture
            self.empr_prec = e
            if (stable or longtemps) and nouveau and self.n < self.max_par_ecran:
                self.empr_capt = e
                self.instable_depuis = None
                return typ, self._enregistrer(img, typ)
            return typ, None
        if not self.capture_faite:
            self.capture_faite = True
            if typ in ZONE_CONTENU:
                e = empreinte(img, ZONE_CONTENU[typ])
                if difference(e, self.deja_vu.get(typ)) < 0.01:   # même page, mêmes chiffres : déjà enregistrée
                    return typ, None
                self.deja_vu[typ] = e
            return typ, self._enregistrer(img, typ)
        return typ, None

    def _enregistrer(self, img, typ):
        self.n += 1
        maintenant = time.localtime()
        jour = time.strftime("%Y-%m-%d", maintenant)
        d = os.path.join(self.dossier, jour)
        os.makedirs(d, exist_ok=True)
        base = time.strftime("%H-%M-%S", maintenant) + "_" + typ
        chemin = os.path.join(d, base + ".png")
        i = 2
        while os.path.exists(chemin):
            chemin = os.path.join(d, f"{base}_{i}.png")
            i += 1
        cv2.imwrite(chemin, img)
        return chemin
