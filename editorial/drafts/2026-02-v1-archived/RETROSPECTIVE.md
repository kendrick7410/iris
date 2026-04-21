# RETROSPECTIVE — Édition Février 2026 (dry-run)

## Ce qui a bien marché

1. **Pipeline bout-en-bout en 39 secondes.** FETCH (4s) → PROCESS (<1s) → DRAFT (28s, 4 API calls) → VISUALIZE (1s) → BUILD (<1s). Pas de timeout, pas de retry nécessaire.
2. **Summary quality "ok" du premier coup.** Sonnet a produit un résumé 4-bullets de 131 mots passant les 4 critères de qualité. Pas besoin du fallback Opus.
3. **3 sections produites sur 3 possibles** (trade skippé car Comext indisponible — comportement attendu). Output obligatoire = présent. Condition de publication remplie.
4. **Manifest complet et cohérent.** Prompt hashes, data periods, model info — tout est là pour la reproductibilité.
5. **4 charts SVG générés** (2 output + 2 prices). Design lisible, source lines en pied.

## Ce qui a accroché

1. **Chart turnover_index : "Not enough timeseries points".** Le chart timeseries attend ≥2 points mais la fiche sales n'expose que current + previous_year (2 points extraits du JSON mais le renderer cherche dans les mauvais champs). Le renderer utilise `data.current` et `data.previous_year` au lieu de la série complète du cache.
2. **Chart turnover_yoy_country : NoneType comparison.** Certains pays ont `yoy_pct: null` quand le mois précédent n'existe pas dans les données. Corrigé par `or 0` dans le tri.
3. **Section sales : pas de YoY dans le texte.** La section cote les index absolus au lieu des mouvements YoY — le LLM a reçu une fiche avec `ytd: null` (janvier = 1 seul mois) et `previous_year.delta_pct: -7.5` mais n'a pas exploité le delta. Le system prompt ne guide pas assez le comportement quand `ytd` est null.

## Top 3 dettes techniques

1. **Le renderer de charts ne lit pas la série temporelle complète.** Il devrait lire le cache brut (`data/cache/YYYY-MM/production.json` → champ `eu27`) pour avoir la série complète, pas seulement la fiche (qui ne contient que current + previous_year). **Fix : passer le cache_dir au renderer en plus du fiches_dir, ou enrichir la fiche avec la série complète.**

2. **La section sales sous-exploite les données.** Quand `ytd` est null et qu'il n'y a qu'un seul mois, le LLM tombe sur un cas non-templated et produit une prose plus faible (ranking par index absolu au lieu du YoY). **Fix : dans `system.md`, ajouter une règle spécifique "for single-month data (January), lead with YoY comparison against January of the previous year".**

3. **Pas de test d'intégration automatisé.** Les tests unitaires passent mais le run end-to-end n'a pas de test automatisé qui vérifie que `edition.md` existe et contient les bonnes sections. **Fix : ajouter `tests/test_pipeline_integration.py` avec un mock des API calls.**
