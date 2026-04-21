# ITERATION DIFF — Fiche 3 Turnover : v1 vs v2

## Texte v1

> ## EU27 chemical sales fell 7.5% in January 2026
> 
> In January 2026, EU27 chemical sales decreased by 7.5% compared to January 2025, with the turnover index reaching 90.8 (2021=100). The sector underperformed total manufacturing, which declined by 1.8% over the same period.
> 
> The decline was widespread across major chemical-producing countries. With 89.3, Germany reported the largest absolute turnover level, down 8.0% compared to January 2025. The Netherlands recorded the steepest decline at 14.2%, reaching 79.0, followed by Belgium at 88.5, down 13.2%. Poland reported 104.6, down 11.7%, while Spain fell 6.9% to 97.6. France showed the most resilient performance at 101.3, declining by 3.1%. Italy reached 94.2, down 6.7% year-on-year.
> 
> {{chart:turnover_index_2021_2026}}
> Source: Cefic analysis based on Eurostat data (sts_intv_m, 2026)
> 
> {{chart:turnover_yoy_by_country}}
> Source: Cefic analysis based on Eurostat data (sts_intv_m, 2026)

## Texte v2

> ## EU27 chemical sales decline by 7.5% in January 2026
> 
> EU27 chemical sales decreased by 7.5% in January 2026 compared to January 2025, with the turnover index reaching 90.8. The decline outpaced total manufacturing, which decreased by 1.8% over the same period.
> 
> The Netherlands experienced the steepest sales decline at 14.2%, followed by Belgium (13.2%) and Poland (11.7%). Germany reported an 8.0% decrease, while Spain declined by 6.9% and Italy by 6.7%. France recorded the smallest decline at 3.1%.
> 
> {{chart:turnover_index_2021_2026}}
> Source: Cefic analysis based on Eurostat data (2026)
> 
> {{chart:turnover_yoy_by_country}}
> Source: Cefic analysis based on Eurostat data (2026)
> 
> These chemical production trends by country show a fragmented Europe.

## Améliorations (v2 vs v1)

| Aspect | v1 | v2 | Verdict |
|---|---|---|---|
| **Source line** | `(sts_intv_m, 2026)` — dataset code visible | `(2026)` — Cefic format | ✅ Corrigé |
| **Jugement qualitatif** | "most resilient performance" | "smallest decline" | ✅ Corrigé |
| **Ranking par mouvement** | Classé par index absolu ("With 89.3, Germany...") | Classé par YoY ("Netherlands steepest at 14.2%") | ✅ Corrigé |
| **Concision** | 941 chars, phrases denses | 753 chars, plus compact | ✅ Amélioré |
| **Index levels inutiles** | "reaching 79.0", "at 88.5", "reported 104.6" | Supprimés — focus sur le % | ✅ Amélioré |

## Régressions (v2 vs v1)

| Aspect | v1 | v2 | Verdict |
|---|---|---|---|
| **"Fragmented Europe" placement** | Absent | Présent mais **après** les charts — devrait être avant | ❌ Mauvais placement |
| **Phrases courtes** | 0 phrases ≤15 mots | "The decline outpaced total manufacturing..." (12 mots si tronqué, mais la phrase complète fait 16 mots). Pas de véritable phrase courte isolée. | ⚠️ Peu amélioré |
| **Heading verb tense** | "fell" (past, direct) | "decline" (present, nominal) — le corpus préfère le passé factuel | ⚠️ Mineur |

## Ce qui reste problématique

1. **"Fragmented Europe" après les charts.** Le modèle a ajouté la phrase mais l'a placée après les source lines. Dans le corpus, la phrase de clôture vient immédiatement après le dernier pays cité, **avant** le chart. C'est un problème de template §6.1 — il faut préciser que la prose d'analyse vient avant les charts, pas après.

2. **Phrases courtes : progrès insuffisant.** Malgré le patch, le modèle ne produit toujours pas de phrases ≤15 mots. Le patch actuel donne des exemples mais ne fournit pas de contrainte structurelle (ex: "la deuxième phrase de chaque section DOIT être ≤15 mots"). À renforcer dans une itération 2.

3. **Densité en baisse.** La v2 omet les index levels absolus — c'est plus propre analytiquement (le mouvement YoY est le message), mais réduit le nombre de data points. Le corpus Cefic donne les deux (valeur + mouvement). Trade-off acceptable.

## Conclusion opérationnelle

Le system prompt v1 patché corrige les **dérives mécaniques** (source line, qualitative judgements, ranking logic). Il ne corrige pas encore les **dérives de rythme** (phrases courtes) ni le **placement structurel** (prose vs charts). Ces deux points nécessitent soit une itération 2 du system prompt, soit un post-processing dans l'orchestrateur Iris.

Le prompt est utilisable pour un prototype. Il n'est pas encore prod-ready pour publication automatique.
