# Notes de conception

## Pourquoi lire l'écran

- Activision n'a pas d'API publique de stats. L'ancienne API non officielle (my.callofduty.com) est coupée, et les sites comme Tracker.gg n'affichent plus que d'anciennes données.
- Lire la mémoire du jeu ou intercepter son trafic réseau, c'est ce que détecte l'anti-triche RICOCHET : exclu.
- Afficher des infos sur le lobby est interdit (Warzone Agent, bloqué depuis la Saison 1 de MW4) : exclu.
- Il reste ce que le jeu affiche à l'écran. C'est la méthode utilisée par les trackers de bureau qui fonctionnent encore.

## Écrans utiles

| Écran | Données |
|---|---|
| Fin de match (VICTOIRE / DÉFAITE) | mode, scores, tableaux des 2 équipes (niveau, pseudo, score, élim., temps obj.), bandeau du joueur (élim./assist., morts, ratio élim./m.) |
| Rapport de bataille | résultat, mode, **carte**, scores, score / élim. / temps obj. du joueur, niveau |
| Carrière › Rapport de combat › Parties récentes | les **10 dernières parties** (mode, carte, résultat, scores, « il y a ») et le détail de la partie sélectionnée (score, élim., morts, ratio É/M, score objectif, dégâts) |
| Rapport de combat › Multijoueur | stats depuis le début : parties, V/D, É/M, score/min, série, record, victoires par mode, 3 meilleures armes |
| Carrière | niveau, prestige |

À savoir :

- Les **morts des autres joueurs** ne s'affichent nulle part. On n'a le K/D que du joueur lui-même.
- Une **défaite pardonnée** ne compte pas dans le V/D du jeu.
- Le jeu garde les 10 dernières parties : une nouvelle inscription peut récupérer cet historique et les stats totales, rien avant.

## Détection des écrans (`ratio-capture/detecteur.py`)

- L'image est ramenée en 1280×720 (recadrage 16:9 au centre). Les modèles sont recherchés à 11 tailles (0,85 à 1,15) pour couvrir les résolutions et l'échelle de l'interface.
- **Fin de match** : on compare le *masque de couleur* du texte de l'en-tête des tableaux (cyan pour la victoire et la défaite, rouge pour l'équipe adverse), avec le bandeau du joueur comme 2e condition. Le masque ne dépend pas du décor animé derrière. Le tableau Tab, en cours de partie, a son en-tête plus haut et ne déclenche pas.
- **Pages de menu** : comparaison des titres en niveaux de gris (seuil 0,75). « RAPPORT DE COMBAT » et « RAPPORT DE BATAILLE » sont départagés sur leur dernier mot.

## Quand capturer (`ratio-capture/moteur.py`)

- L'écran doit être stable depuis 1 s, pour laisser finir les animations. Une absence de moins de 2,5 s est tolérée.
- Fin de match : une image par apparition.
- Parties récentes : une image chaque fois que le panneau de détail change. On compte les pixels qui ont franchement changé, ce qui ignore le bruit mais voit des chiffres différents.
- Rapport de combat, Carrière, Rapport de bataille : pas de nouvelle image si la zone des chiffres est identique à la dernière capture.

## Résultats des tests

- Enregistrement de 5 min (720p) simulé à 0,5 s d'intervalle : exactement 3 captures (Carrière, Rapport de combat, fin de match), aucune fausse détection en partie, dans les menus ou sur le tableau Tab.
- Marge de détection de la fin de match : ≥ 0,85 sur le vrai écran contre ≤ 0,34 sur 1 461 autres images.
- 1er test réel sur PC (1920×1080, DXGI) : défaite, Rapport de bataille, Rapport de combat et Carrière capturés tout seuls, sans erreur.

## Lecture locale (`lecteur/`)

- L'OCR générique confond le **zéro barré** des tableaux avec 8, 9 ou 6, et la police dorée très étroite du Rapport de combat (5 lu 9, 17 lu 7).
- Solution : apprendre les chiffres de chaque police à partir d'écrans dont on connaît les valeurs, puis reconnaître par ressemblance (exemple le plus proche). Des contrôles de cohérence suivent : ratio = élim. ÷ morts, V/D = victoires ÷ défaites, moyenne = élim. ÷ parties.
- Validation croisée sur une seule partie en 720p : 93 % des nombres justes sur les tableaux, 85 % sur le Rapport de combat. Les erreurs viennent surtout du manque d'exemples.

## Suite prévue

1. Écrans de fin Warzone et DMZ.
2. Serveur dédié (par exemple Supabase), avec connexion Battle.net ou Steam : chaque partie envoyée directement, sans glisser-déposer.
