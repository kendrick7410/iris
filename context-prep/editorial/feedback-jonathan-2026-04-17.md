Je réponds à tes 3 questions éditoriales, puis je te dis ce que je vois dans les dérives restantes.
Q1 — Chaque chart doit-il être précédé d'un commentaire analytique ?
Oui. Le corpus Cefic le fait systématiquement, et c'est une différence structurelle importante. Un chart sans prose qui le précède donne une impression de "data dump" — exactement le travers qu'Iris doit éviter pour passer pour une publication éditoriale, pas un dashboard.
Règle à ajouter en §6.1 :

Every chart must be preceded by at least one analytical sentence that introduces what the chart shows or highlights its key finding. Charts are never stacked without prose between them. If two charts appear consecutively, insert a transition sentence — typically anchored on a figure from the second chart.

C'est aussi ce qui résout le problème "charts empilés" que tu as observé dans la fiche 1.
Q2 — Heading avec pre-crisis ou YoY ?
Règle de préférence : le benchmark le plus frappant pour ce mois. Pas de règle fixe.
Logique :

Si le YoY est fort (≥5%), le heading porte le YoY — c'est le mouvement, c'est ce qui fait l'actualité du mois
Si le YoY est faible (<2%) mais que l'écart pre-crisis est structurel et important (≥10%), le heading porte le pre-crisis — c'est le constat de long terme qui reste le signal
Si les deux sont forts, le YoY prime (c'est le mouvement du mois qui justifie une publication mensuelle)
Si les deux sont faibles, le heading porte la stabilité : "EU27 chemical production remains broadly stable in February 2026" — et c'est OK, tout les mois ne sont pas des mois à constat fort

Règle à ajouter en §2.6 ou nouvelle §2.7 :

The heading figure is the most editorially salient benchmark for the period: the YoY change when movement is material (|≥2%|), the pre-crisis gap when the structural finding dominates (movement <2% and pre-crisis gap ≥10%), or the stability observation when both are muted.

Q3 — "The decline was widespread" — autorisée ?
Non, pas comme ça. Cette formulation est une tentation LLM classique : synthétiser sans chiffrer. Le corpus Cefic n'en a pas besoin parce qu'il gère le rythme autrement — phrases courtes qui contiennent quand même un chiffre.
Contre-exemples de phrases courtes chiffrées qui rythment sans trahir le Pattern 1 :

"The decline spanned six of seven reporting countries."
"Only France posted a gain, at 1.1%."
"Spread: 10.7 percentage points between Netherlands and France."
"Pharmaceuticals also fell, down 8.6%."

Toutes sont courtes (≤10 mots), toutes contiennent un chiffre ou un comptage. C'est ça la signature Cefic, pas la synthèse vague.
Règle à ajouter en §2.1 (complète ton Patch 2) :

Short sentences must still carry a number, a count, or an entity name. A short sentence without any quantifier ("The decline was widespread", "Pressure remained high") is vague commentary and violates Pattern 1. Acceptable short sentences: "Six of seven countries posted declines." / "Only France gained." / "Pharmaceuticals fell more, at 8.6%."

Sur les dérives restantes
Rythme des phrases courtes (problème partiellement corrigé). Mon intuition : ce n'est pas un problème de prompt, c'est un problème structurel de LLM. Les modèles aiment les phrases composées. Une contrainte explicite "au moins une phrase ≤15 mots dans chaque paragraphe de plus de 3 phrases" serait plus efficace que "au moins une par section". C'est plus mécanique, donc plus testable, donc mieux respecté.
Placement prose-avant-charts. Traité par ma réponse à Q1. Règle claire dans §6.1.
Fragmented Europe mal placé en v2. À regarder dans la fiche v2. Probablement un patch de placement, pas de contenu. Peux-tu me montrer la v2 de la fiche 3 où tu as observé ça ?
Ce que je te propose maintenant
Trois chemins possibles, tu choisis :
A. On finalise system.md v2 avec les réponses aux 3 questions + la précision sur les phrases courtes chiffrées. Je te rédige les 3-4 patches exacts à passer à Claude Code, il les applique, on refait un test sur la fiche 1 uniquement pour valider qu'on ne régresse pas, et on déclare le system prompt stable pour v1.
B. On stoppe le polish éditorial ici (utilisable pour prototyper, ton verdict) et on passe à l'orchestrateur : comment Iris passe d'un .json de fiche à un article complet avec plusieurs sections, comment il gère les charts, comment il génère le site.
C. On attend Yaghi et on reprend tout bootstrap structurel.
Je recommande A puis B dans la même session si tu as l'énergie, sinon A seul et B à la session suivante. Ça ferme le chantier éditorial proprement avant qu'on touche à l'infra.