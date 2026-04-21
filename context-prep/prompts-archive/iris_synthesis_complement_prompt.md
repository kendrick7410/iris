# Complément SYNTHESIS avant Livrable 2

> Petit add-on avant d'attaquer le system prompt. 20-30 min.

---

`SYNTHESIS.md` est solide, on va l'exploiter pour le Livrable 2. Avant, trois angles morts à couvrir. Ajoute-les comme patterns 16, 17, 18 dans le même fichier (même format : description + exemples + implication).

## Pattern 16 — Longueur et structure de phrase

Mesure sur au moins 4 paragraphes extraits du corpus (2 CT + 2 F&F) :
- Moyenne de mots par phrase
- Médiane
- Ratio phrases simples / phrases avec subordonnées
- Y a-t-il un usage notable des phrases courtes pour marquer un point (punch), ou c'est uniformément analytique ?

Pourquoi ça compte : les LLM produisent spontanément des phrases longues avec 2-3 subordonnées. Si le corpus Cefic est en phrases plus courtes/moyennes, il faut l'imposer explicitement dans le system prompt.

## Pattern 17 — Inventaire des connecteurs logiques

Extrais du corpus la liste des connecteurs effectivement utilisés (contraste, addition, cause, conséquence, temporalité). Classe par fréquence approximative : 3-5 connecteurs dominants, puis les secondaires.

Produis aussi une **liste noire** des connecteurs typiquement LLM qui n'apparaissent pas dans le corpus : *furthermore*, *moreover*, *additionally*, *in conclusion*, *notably*, *it is worth noting*, *importantly*, etc. Vérifie leur absence réelle — si l'un apparaît, ne le mets pas dans la liste noire.

Pourquoi ça compte : c'est la texture discursive. Un LLM qui commence une phrase par *Furthermore,* est immédiatement détectable.

## Pattern 18 — Gestion des données partielles, préliminaires, ou décalées

Cherche dans le corpus comment Cefic traite :
- Les données préliminaires ou révisées (formulations-type ?)
- Les indicateurs trimestriels cités dans un contexte mensuel
- Les périodes incomplètes (ex: "first 8 months of 2025" — déjà vu dans Pattern 3, mais vérifie s'il y a un pattern plus large)
- Les cas où une donnée manque ou est dépassée

Si le corpus ne traite pas explicitement ces cas (possible — les publications Cefic paraissent à cadence lente), note-le et propose une règle à inventer pour Iris, alignée sur le style observé.

Pourquoi ça compte : Iris étant mensuel, certains indicateurs Eurostat auront 2-3 mois de latence. Le mois 1, il y aura des trous. Sans règle éditoriale claire, le LLM va soit inventer, soit produire une tournure maladroite qui signale l'automatisation.

## Bonus — Relecture critique de deux patterns existants

Revois ces deux points et ajuste si tu es d'accord :

**Pattern 8 ("since March 2022")** — proposition : passer de "imposer la date verbatim" à "imposer une règle plus générale : ancrer les ruptures structurelles sur une date précise (mois + année), pas une période floue ('post-pandemic', 'recent years'). La date de référence actuelle est mars 2022, à réévaluer si un nouveau point d'inflexion émerge."

**Pattern 10 (3e personne stricte)** — question : le Q4 2025 utilise un "we" ponctuel. On l'interdit totalement à Iris (risque : divergence détectable avec le rapport humain) ou on autorise 1 "we" max par édition dans des conditions très contraintes (ex: pour souligner un point analytique majeur, jamais en ouverture/clôture) ? Propose une règle et argumente.

## Livrable

Mise à jour de `SYNTHESIS.md` avec les patterns 16-18 + les deux ajustements. Pas de nouveau fichier. Présente-moi les sections ajoutées/modifiées.

Ensuite seulement, Livrable 2.
