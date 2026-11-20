# Tracker MW4 Multi

Stats Call of Duty : Modern Warfare 4 (multijoueur) pour ta team, façon op.gg : profils, K/D, V/D, historique des matchs, groupes avec code d'invitation et comparatifs entre potes.

Activision ne propose aucune API publique de stats. Le projet lit donc **ce qui s'affiche à l'écran**, comme Medal ou Discord, sans toucher au jeu.

## Comment ça marche

```
 Pendant que tu joues                         Après la session
 ┌──────────────────────┐   images PNG   ┌──────────────────────────────┐
 │  Ratio Capture (PC)  │ ─────────────► │  Ratio Teams (page web)       │
 │  repère tout seul    │  glisser-      │  Claude lit les captures,     │
 │  les écrans de stats │  déposer       │  tu vérifies, c'est enregistré│
 └──────────────────────┘                │  profil · matchs · groupe     │
                                         └──────────────────────────────┘
```

1. **Ratio Capture** tourne en fond sur ton PC. Deux fois par seconde, il regarde l'écran et garde une image quand il reconnaît :
   - l'écran de **fin de match** (VICTOIRE / DÉFAITE avec le tableau des équipes) ;
   - le **Rapport de bataille** qui suit (il donne la carte) ;
   - **Carrière › Rapport de combat › Parties récentes** (une image par partie consultée) ;
   - le **Rapport de combat** (stats depuis le début) et la page **Carrière**.
2. Après ta session, tu glisses les images dans **Ratio Teams**. Claude les lit, tu vérifies les chiffres, et tout s'ajoute à ton profil. Un même match vu sur plusieurs écrans est fusionné, pas dupliqué.

## Ce que le logiciel ne fait jamais

- Il ne lit pas la mémoire du jeu, n'intercepte pas le réseau et n'injecte rien.
- Il n'envoie aucun clic ni aucune touche au jeu.
- Il ne donne aucune info sur le lobby avant ou pendant une partie. C'est ce que fait Warzone Agent, bloqué par RICOCHET depuis la Saison 1 de MW4.

## Installer Ratio Capture (Windows)

**Option 1 : le .exe**
Onglet **Actions** › « Compiler Ratio Capture (.exe Windows) » › dernier lancement réussi › télécharge **RatioCapture-windows**. Dézippe-le, puis lance `RatioCapture.exe`.

**Option 2 : depuis les sources**
1. Télécharge le dossier `ratio-capture/`.
2. Double-clique sur `Lancer Ratio Capture.bat`. Au premier lancement, il installe Python 3.12 si besoin, puis les dépendances (1 à 3 minutes).
3. Laisse la fenêtre ouverte pendant que tu joues. Mets le jeu en **plein écran sans bordure**.

Les captures vont dans `ratio-capture/captures/AAAA-MM-JJ/`. Le bouton **Importer** ouvre Ratio Teams et le dossier du jour.

## Contenu du dépôt

| Dossier | Contenu |
|---|---|
| `ratio-capture/` | Le logiciel Windows. `detecteur.py` reconnaît les écrans, `moteur.py` décide quand capturer, `ratio_capture.py` gère la fenêtre et la capture d'écran (DXGI, avec repli sur mss). `modeles/` contient les modèles d'images découpés dans de vraies captures du jeu. |
| `web/` | La page **Ratio Teams** : inscription, profil, matchs, groupes, import des captures. Elle tourne comme artifact claude.ai, car elle utilise la base de données, l'identité et la lecture d'images fournies par claude.ai. |
| `lecteur/` | Prototype de lecture locale, sans Claude. Il reconnaît les chiffres avec les polices exactes du jeu (le zéro barré trompe l'OCR classique) et fait des contrôles de cohérence. |
| `docs/` | Notes de conception : écrans utiles, choix techniques, résultats des tests. |

## Tester la détection

```bat
cd ratio-capture
.venv\Scripts\python.exe ratio_capture.py --image chemin\vers\capture.png
.venv\Scripts\python.exe ratio_capture.py --video chemin\vers\partie.mp4
```

`--image` affiche l'écran reconnu et les scores. `--video` simule le logiciel sur un enregistrement (Medal, NVIDIA…) et liste les captures qu'il aurait faites.

## Confidentialité

- Les captures restent sur ton PC jusqu'à ce que tu les importes.
- Dans Ratio Teams, seuls les joueurs inscrits apparaissent avec leur pseudo. Les autres joueurs des tableaux restent « Joueur non inscrit » : leurs pseudos ne sont pas enregistrés.
- Aucune capture ni donnée de joueur n'est stockée dans ce dépôt.

## Limites actuelles

- MW4 **multijoueur** seulement. Warzone et DMZ viendront avec des captures de leurs écrans de fin.
- Écran principal seulement, au format 16:9 de préférence (21:9 et 16:10 sont recadrés au centre).
- L'import est un glisser-déposer. L'envoi direct de chaque partie demandera un serveur dédié, avec une connexion Battle.net ou Steam.

---

Projet indépendant, non affilié à Activision. Call of Duty est une marque d'Activision Publishing, Inc.
