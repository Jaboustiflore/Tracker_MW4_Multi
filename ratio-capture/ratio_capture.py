"""Ratio Capture : enregistre tout seul les écrans de stats de Call of Duty MW4 pendant que tu joues.

- Regarde l'écran deux fois par seconde (comme Medal, OBS ou Discord).
- Quand un écran de fin de match, « Parties récentes », le Rapport de combat ou la Carrière apparaît,
  il en garde une image dans le dossier captures/ (un sous-dossier par jour).
- À la fin de la session, tu glisses ces images dans Ratio Teams : elles sont lues et ajoutées à ton profil.

Il lit uniquement ce qui s'affiche à l'écran : il ne touche ni au jeu, ni à sa mémoire, ni au réseau,
et n'envoie aucun clic ni aucune touche.

Lancement normal : double-clic sur « Lancer Ratio Capture.bat » (ou sur RatioCapture.exe).
Tests : python ratio_capture.py --image capture.png   |   python ratio_capture.py --video partie.mp4
"""
import json
import os
import queue
import sys
import threading
import time
import traceback
import webbrowser

if getattr(sys, "frozen", False):
    # version .exe : captures et journal à côté de l'exécutable
    ICI = os.path.dirname(sys.executable)
else:
    ICI = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, ICI)
DOSSIER_CAPTURES = os.path.join(ICI, "captures")
JOURNAL = os.path.join(ICI, "ratio_capture.log")
URL_RATIO = "https://claude.ai/artifact/X9gyTphT2ZoE97NghPFSZy"
INTERVALLE = 0.5   # secondes entre deux regards sur l'écran

NOMS = {"fin_match": "Fin de match", "parties_recentes": "Parties récentes",
        "rapport_combat": "Rapport de combat", "carriere": "Carrière", "rapport_bataille": "Rapport de bataille"}


def journal(msg):
    try:
        if os.path.exists(JOURNAL) and os.path.getsize(JOURNAL) > 1_000_000:
            os.replace(JOURNAL, JOURNAL + ".ancien")
        with open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------- capture d'écran
class Ecran:
    """Capture de l'écran principal : DXGI (dxcam) si possible, sinon mss."""

    def __init__(self):
        self.mode = None
        self.dernier = None
        try:
            import dxcam
            self.cam = dxcam.create(output_color="BGR")
            if self.cam is None:
                raise RuntimeError("dxcam indisponible")
            self.mode = "dxgi"
        except Exception as e:  # noqa: BLE001
            journal(f"dxcam indisponible ({e}), passage à mss")
            import mss
            self.sct = mss.mss()
            self.mode = "mss"

    def passer_mss(self, raison):
        """Bascule sur la capture standard (si DirectX échoue ou ne renvoie que du noir)."""
        if self.mode == "mss":
            return False
        journal(f"passage à mss : {raison}")
        try:
            self.cam.release()
        except Exception:  # noqa: BLE001
            pass
        import mss
        self.sct = mss.mss()
        self.mode = "mss"
        self.dernier = None
        return True

    def image(self):
        import numpy as np
        import cv2
        if self.mode == "dxgi":
            try:
                f = self.cam.grab()
            except Exception as e:  # noqa: BLE001
                self.passer_mss(f"erreur dxcam {e}")
                return self.image()
            if f is not None:          # None = l'écran n'a pas changé depuis la dernière image
                self.dernier = f
            return self.dernier
        mon = self.sct.monitors[1]
        img = np.asarray(self.sct.grab(mon))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


# ---------------------------------------------------------------- fenêtre
def lancer_fenetre():
    import tkinter as tk
    from tkinter import font as tkfont

    from moteur import Capteur

    q = queue.Queue()
    etat = {"pause": False, "stop": False}

    def boucle():
        try:
            ecran = Ecran()
            q.put(("mode", ecran.mode))
            capteur = Capteur(DOSSIER_CAPTURES)
            while not etat["stop"]:
                if etat["pause"]:
                    time.sleep(0.3)
                    continue
                t0 = time.monotonic()
                img = ecran.image()
                if img is not None:
                    noir = capteur.ecran_noir(img, t0)
                    if noir and ecran.passer_mss("image noire depuis 10 s"):
                        q.put(("mode", ecran.mode))
                        capteur.noir_depuis = None
                        continue
                    typ, chemin = capteur.traiter(img, t0)
                    q.put(("etat", typ, chemin, noir))
                    if chemin:
                        journal(f"capture {typ} -> {chemin}")
                time.sleep(max(0.05, INTERVALLE - (time.monotonic() - t0)))
        except Exception:  # noqa: BLE001
            journal("ERREUR\n" + traceback.format_exc())
            q.put(("erreur", traceback.format_exc().strip().splitlines()[-1]))

    FOND, CARTE, LIGNE, TEXTE, DOUX, ACCENT = "#0E1218", "#131821", "#242C3A", "#E9EDF3", "#A3ADBB", "#F5C542"
    root = tk.Tk()
    root.title("Ratio Capture")
    root.configure(bg=FOND)
    root.geometry("440x560")
    root.minsize(400, 520)
    base = tkfont.nametofont("TkDefaultFont")
    base.configure(family="Segoe UI", size=10)
    titre_f = ("Segoe UI Semibold", 15)

    def carte(parent, **kw):
        return tk.Frame(parent, bg=CARTE, highlightbackground=LIGNE, highlightthickness=1, **kw)

    entete = tk.Frame(root, bg=FOND)
    entete.pack(fill="x", padx=16, pady=(14, 8))
    tk.Label(entete, text="RATIO", bg=ACCENT, fg="#11141A", font=("Segoe UI Black", 11), padx=8, pady=2).pack(side="left")
    tk.Label(entete, text="  Capture automatique", bg=FOND, fg=TEXTE, font=titre_f).pack(side="left")

    c1 = carte(root)
    c1.pack(fill="x", padx=16, pady=6)
    ligne_statut = tk.Frame(c1, bg=CARTE)
    ligne_statut.pack(fill="x", padx=12, pady=(12, 4))
    point = tk.Canvas(ligne_statut, width=12, height=12, bg=CARTE, highlightthickness=0)
    rond = point.create_oval(1, 1, 11, 11, fill="#8EC3FF", outline="")
    point.pack(side="left")
    statut = tk.Label(ligne_statut, text="Démarrage…", bg=CARTE, fg=TEXTE, font=("Segoe UI Semibold", 11), anchor="w")
    statut.pack(side="left", padx=8)
    detail = tk.Label(c1, text="", bg=CARTE, fg=DOUX, anchor="w", justify="left", wraplength=390)
    detail.pack(fill="x", padx=12, pady=(0, 12))

    c2 = carte(root)
    c2.pack(fill="both", expand=True, padx=16, pady=6)
    compteur = tk.Label(c2, text="Captures aujourd'hui : 0", bg=CARTE, fg=TEXTE, font=("Segoe UI Semibold", 11), anchor="w")
    compteur.pack(fill="x", padx=12, pady=(12, 6))
    liste = tk.Listbox(c2, bg=FOND, fg=TEXTE, selectbackground=LIGNE, highlightthickness=0, borderwidth=0,
                       activestyle="none", font=("Segoe UI", 10), height=8)
    liste.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    boutons = tk.Frame(root, bg=FOND)
    boutons.pack(fill="x", padx=16, pady=6)

    def bouton(parent, texte, cmd, principal=False):
        b = tk.Button(parent, text=texte, command=cmd, relief="flat", cursor="hand2", padx=10, pady=8,
                      bg=ACCENT if principal else "#1A2130", fg="#11141A" if principal else TEXTE,
                      activebackground="#FFD45E" if principal else LIGNE, activeforeground="#11141A" if principal else TEXTE,
                      font=("Segoe UI Semibold", 10))
        return b

    def basculer_pause():
        etat["pause"] = not etat["pause"]
        b_pause.configure(text="Reprendre" if etat["pause"] else "Mettre en pause")
        maj_statut(None, False)

    def ouvrir_dossier():
        os.makedirs(DOSSIER_CAPTURES, exist_ok=True)
        jour = os.path.join(DOSSIER_CAPTURES, time.strftime("%Y-%m-%d"))
        os.startfile(jour if os.path.isdir(jour) else DOSSIER_CAPTURES)  # type: ignore[attr-defined]

    def importer():
        ouvrir_dossier()
        webbrowser.open(URL_RATIO + "#importer")

    b_pause = bouton(boutons, "Mettre en pause", basculer_pause)
    b_pause.pack(side="left", expand=True, fill="x", padx=(0, 6))
    bouton(boutons, "Ouvrir le dossier", ouvrir_dossier).pack(side="left", expand=True, fill="x", padx=(0, 6))
    bouton(boutons, "Importer", importer, principal=True).pack(side="left", expand=True, fill="x")

    tk.Label(root, text="« Importer » ouvre Ratio Teams et le dossier du jour : glisse les images dans la page.",
             bg=FOND, fg=DOUX, wraplength=400, justify="left").pack(fill="x", padx=16, pady=(4, 0))
    tk.Label(root, text="Lit uniquement l'écran. Ne touche ni au jeu, ni à sa mémoire, ni au réseau.",
             bg=FOND, fg="#8C97A7", wraplength=400, justify="left", font=("Segoe UI", 9)).pack(fill="x", padx=16, pady=(6, 12))

    infos = {"mode": None, "dernier": None, "noir": False, "n": 0, "erreur": None}

    def compter_aujourdhui():
        d = os.path.join(DOSSIER_CAPTURES, time.strftime("%Y-%m-%d"))
        if not os.path.isdir(d):
            return []
        return sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))

    def rafraichir_liste():
        fichiers = compter_aujourdhui()
        infos["n"] = len(fichiers)
        compteur.configure(text=f"Captures aujourd'hui : {len(fichiers)}")
        liste.delete(0, "end")
        for f in reversed(fichiers[-50:]):
            heure = f[:8].replace("-", ":")
            typ = f[9:-4].split("_")
            nom = NOMS.get("_".join(t for t in typ if not t.isdigit()), f)
            liste.insert("end", f"  {heure}   {nom}")
        if not fichiers:
            liste.insert("end", "  Aucune capture pour l'instant aujourd'hui.")

    def maj_statut(typ, noir):
        if infos["erreur"]:
            point.itemconfigure(rond, fill="#FFAD8A")
            statut.configure(text="Problème")
            detail.configure(text=f"{infos['erreur']}\nRelance le logiciel. Si ça recommence, envoie le fichier ratio_capture.log à Claude.")
        elif etat["pause"]:
            point.itemconfigure(rond, fill="#8C97A7")
            statut.configure(text="En pause")
            detail.configure(text="Aucune capture ne sera faite tant que tu ne cliques pas sur Reprendre.")
        elif noir:
            point.itemconfigure(rond, fill="#FFAD8A")
            statut.configure(text="Écran capturé tout noir")
            detail.configure(text="Dans les options d'affichage du jeu, choisis « Plein écran sans bordure », puis reviens ici.")
        else:
            point.itemconfigure(rond, fill="#8EC3FF")
            statut.configure(text="Actif")
            msg = "En attente d'un écran de fin de match, de « Parties récentes » ou du Rapport de combat."
            if typ:
                msg = f"Écran reconnu : {NOMS.get(typ, typ)}."
            elif infos["dernier"]:
                msg += f"\nDernière capture : {infos['dernier']}."
            detail.configure(text=msg)

    def lire_file():
        typ_vu, noir = infos.get("typ"), infos["noir"]
        nouvelle = False
        try:
            while True:
                m = q.get_nowait()
                if m[0] == "mode":
                    infos["mode"] = m[1]
                elif m[0] == "erreur":
                    infos["erreur"] = m[1]
                elif m[0] == "etat":
                    _, typ_vu, chemin, noir = m
                    infos["noir"] = noir
                    infos["typ"] = typ_vu
                    if chemin:
                        nouvelle = True
                        infos["dernier"] = f"{NOMS.get(typ_vu, typ_vu)} à {time.strftime('%H:%M')}"
        except queue.Empty:
            pass
        if nouvelle:
            rafraichir_liste()
        maj_statut(typ_vu, noir)
        root.after(300, lire_file)

    def fermer():
        etat["stop"] = True
        root.after(200, root.destroy)

    root.protocol("WM_DELETE_WINDOW", fermer)
    rafraichir_liste()
    threading.Thread(target=boucle, daemon=True).start()
    root.after(300, lire_file)
    root.mainloop()


# ---------------------------------------------------------------- outils Windows
def preparer_windows():
    """Netteté sur les écrans à haute résolution, priorité basse pour ne pas toucher aux FPS, une seule instance."""
    if os.name != "nt":
        return True
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass
    try:
        k32 = ctypes.windll.kernel32
        k32.SetPriorityClass(k32.GetCurrentProcess(), 0x00004000)  # BELOW_NORMAL_PRIORITY_CLASS
        preparer_windows.mutex = k32.CreateMutexW(None, False, "RatioCaptureUneSeuleFois")
        if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            ctypes.windll.user32.MessageBoxW(None, "Ratio Capture est déjà ouvert.", "Ratio Capture", 0x40)
            return False
    except Exception:  # noqa: BLE001
        pass
    return True


# ---------------------------------------------------------------- tests en ligne de commande
def tester_image(chemin):
    import cv2
    from detecteur import detecter
    typ, s = detecter(cv2.imread(chemin))
    print(json.dumps({"fichier": chemin, "ecran": typ, "scores": {k: round(v, 3) for k, v in s.items()}}, ensure_ascii=False, indent=2))


def tester_video(chemin):
    import cv2
    from moteur import Capteur
    cap = cv2.VideoCapture(chemin)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    pas = max(1, round(fps * INTERVALLE))
    dossier = os.path.join(ICI, "captures_test")
    c = Capteur(dossier)
    i = 0
    while True:
        if not cap.grab():
            break
        if i % pas == 0:
            ok, f = cap.retrieve()
            if ok:
                typ, ch = c.traiter(f, i / fps)
                if ch:
                    print(f"{i / fps:7.1f} s  {NOMS.get(typ, typ):18s} -> {ch}")
        i += 1
    print(f"Terminé : {i / fps:.0f} s de vidéo analysées. Images dans {dossier}")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--image":
        tester_image(sys.argv[2])
    elif len(sys.argv) >= 3 and sys.argv[1] == "--video":
        tester_video(sys.argv[2])
    else:
        if preparer_windows():
            journal("démarrage")
            lancer_fenetre()
