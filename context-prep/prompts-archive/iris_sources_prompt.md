# Prompt — Spécification des sources de données d'Iris

> À coller dans la session Claude Code en cours.
> On termine la couche "données" avant le Livrable 3. Ensuite on aura des fiches factices *réalistes* pour stress-tester le `system.md`.

---

Avant de passer au Livrable 3, on cadre les sources de données. Objectif : un document unique, complet, qui servira de référence quand Iris ira chercher les chiffres du mois.

## Ne touche à rien d'autre

- Pas de modification de `SYNTHESIS.md` ni de `system.md`.
- Pas de création de structure Iris définitive — on est toujours en `context-prep/`.
- Pas d'écriture de fetcher Python fonctionnel. Juste la spec + tests de connectivité.

## Livrable : `context-prep/data-sources/SOURCES.md`

Document unique, structuré exactement comme ci-dessous.

### Section 1 — Overview

Tableau récapitulatif des sources pour la v1, à remplir :

| Source | Dataset/Artifact | Frequency | Typical latency | Access method | Feeds Iris section |
|---|---|---|---|---|---|
| Eurostat | sts_inpr_m | monthly | ~45 days | JSON API | Output |
| Eurostat | sts_inppd_m | monthly | ~45 days | JSON API | Producer prices |
| Eurostat | sts_intv_m | monthly | ~45 days | JSON API | Turnover |
| Eurostat | nama_10_gdp | quarterly | ~70 days | JSON API | Economic climate |
| DG ECFIN BCS | NACE C20 subsector | monthly | ~5 days | XLSX / new data browser | Business climate, Capacity utilisation |
| Cefic Comext ETL | comext_export.parquet + dimensions | weekly refresh, monthly data, ~45 day Eurostat lag | Parquet files on Yaghi | Trade (exports, imports, trade balance) |

### Section 2 — Eurostat datasets (4 datasets)

Pour **chacun** des 4 datasets (sts_inpr_m, sts_inppd_m, sts_intv_m, nama_10_gdp) :

1. **URL API exacte** (endpoint dissemination v1 JSON).
2. **Paramètres recommandés** pour Iris : `geo=EU27_2020`, `nace_r2=C20` (+ benchmarks C21, C24, C29), `unit=...`, `s_adj=SCA`, `time=...`. Précise le paramètre `unit` attendu par dataset (I15 pour production index, etc.).
3. **Structure de réponse** : JSON-stat, clés importantes (`value`, `dimension`, `index`).
4. **Fréquence et latence** : fréquence de publication, latence typique Eurostat (quand le mois M est-il réellement disponible ?).
5. **Test de connectivité** : lance un appel réel depuis ton environnement actuel, documente la réponse (status code, taille, dernière période disponible). Si ça échoue, documente l'erreur exacte. Rappel : `SYNTHESIS.md` note que le test initial sur `sts_inpr_m` a retourné des valeurs vides — il faut débugger.
6. **Indicateurs dérivés** qu'Iris calculera à partir du dataset (YoY growth, MoM, index vs 2019, etc.), en cohérence avec les patterns de `SYNTHESIS.md` (dual-period, fenêtre YTD).

### Section 3 — DG ECFIN Business and Consumer Surveys

URL racine : https://economy-finance.ec.europa.eu/economic-forecast-and-surveys/business-and-consumer-surveys/download-business-and-consumer-survey-data/subsector-data_en

1. **Dataset principal** : subsector NACE C20 (chimie).
2. **Datasets comparatifs (benchmarks) pour Iris** : NACE C21 (pharma), C24 (métaux de base), C29 (auto). Ce sont les industries de référence que Cefic utilise implicitement pour situer la chimie dans son écosystème.
3. **Variables Iris utilise** : confidence indicator, capacity utilisation (trimestriel), production expectations, order books, selling price expectations. Précise pour chaque variable : fréquence (mensuelle ou trimestrielle), unité, échelle (balance of opinion).
4. **Format d'accès** :
   - Téléchargement XLSX/ZIP historique (stable, documenté)
   - Nouveau data browser (en phase de test, à évaluer)
   - Priorité pour Iris : commence par le XLSX si stable, migrer vers l'API SDMX quand elle sera hors beta.
5. **Cadence de publication** : mensuelle, vers le 25-30 du mois pour le mois courant. Beaucoup plus frais que les séries Eurostat classiques.
6. **Test de connectivité** : identifie l'URL exacte du fichier XLSX subsector, vérifie qu'il est téléchargeable (HEAD request au minimum), note sa taille et sa date de dernière modification.

### Section 4 — Cefic Comext ETL

Lis attentivement :
- https://comext.status.cefic.org/
- https://comext.status.cefic.org/methodology.html

Documente dans `SOURCES.md` :

1. **Contrat Iris ↔ Comext** : Iris lit **uniquement** les 3 fichiers Parquet produits par le pipeline Comext existant. Jamais de requête Postgres directe, jamais de `run_etl.py`, jamais de réécriture du pipeline. Ce découplage est **non-négociable**.

2. **Fichiers consommés** :
   - `comext_export.parquet` — fact table, schéma `period, declarant, partner, product_nc, cpa2015, chapter_cn, flow, flow_label, value_in_euros, quantity_in_kg`
   - `partner_dim.parquet` — dimensions partenaires (labels EN/FR/DE)
   - `product_dim.parquet` — hiérarchie CN complète
   
   Chemin exact : à identifier sur Yaghi quand Claude Code y aura accès. Pour l'instant, paramétrer via `COMEXT_DATA_PATH` dans `.env.example`.

3. **Filtres appliqués en amont** (à ne pas refaire dans Iris) :
   - Chapitres CN 28-39 et 20-21 (chimie + chimie-adjacente, 1369 substances via `SubstanceId.csv`)
   - EU27 déclarants uniquement, GB exclu, déclarant flatten à `'EU'`
   - Partenaires EU27 agrégés à `'EU27'`, non-EU27 gardent leur code ISO

4. **Cadence** : refresh lundi 06:00 CEST, données Eurostat latence ~45 jours.

5. **Implication planning** : le cron Iris (quand il tournera sur Yaghi) doit être planifié **après** le refresh Comext du lundi. Proposition : mardi 09:00. À inscrire dans `CLAUDE.md`.

6. **Test de fraîcheur** : depuis ton PC, `https://comext.status.cefic.org/` permet de voir la dernière période chargée. Note-la dans `SOURCES.md` au moment du test, avec horodatage.

7. **Indicateurs Iris depuis Comext** : extra-EU exports (`declarant=EU, partner NOT IN ('EU27'), flow=2`), extra-EU imports (flow=1), trade balance (exports - imports), ranking partners (Pattern 6), ranking sub-sectors par chapitre CN (Pattern 6).

### Section 5 — Sources réservées pour v1.1

Liste courte, non implémentée :
- OECD (`stats.oecd.org`) — benchmarks internationaux
- IEA (`iea.org`) — energy intensity, carbon intensity
- World Bank (`data.worldbank.org`) — commerce global, prix matières premières
- UN Comtrade — alternative/complément à Comext pour partenaires extra-européens spécifiques

Pour chacune : une phrase sur l'usage futur, et si une clé API est requise. Pas de test.

### Section 6 — Limites, caveats, questions ouvertes

- Révisions Eurostat : les mois passés sont republiés corrigés plusieurs fois par an. Iris doit-il re-générer les anciennes éditions si une série est révisée, ou vit-on avec le snapshot d'origine ? Proposition à argumenter.
- Cellules supprimées Comext (flux < 100€ ou confidentiels) : pas de flag, rows absentes. Impact sur les totaux à noter.
- Brexit : UK dans les données en EU27 jusqu'à déc 2020, puis tiers. Iris doit traiter UK comme partenaire tiers partout — vérifier que c'est bien le cas via le pipeline Comext (la doc dit oui).
- BCS subsector : le nouveau data browser est en phase de test — si on commence par XLSX, prévoir un point de bascule.
- Test `sts_inpr_m` qui a renvoyé des valeurs vides (DISCOVERY.md) — à débugger maintenant, pas plus tard. C'est bloquant pour le Livrable 3.

### Section 7 — Gabarit de fiche mensuelle Iris

À la fin de `SOURCES.md`, un schéma JSON du "data block" que l'orchestrateur Iris passera au LLM rédacteur (user message) :

```json
{
  "period": {
    "month": "2026-02",
    "publication_date": "2026-05-01",
    "window": "January-February 2026"
  },
  "indicators": {
    "output": {
      "current": { "value": 98.4, "unit": "index 2015=100", "period": "2026-02" },
      "benchmarks": {
        "yoy": { "value": 96.1, "delta_pct": 2.4 },
        "pre_crisis_2019": { "value": 108.7, "delta_pct": -9.5 }
      },
      "sub_sectors": { "C21_pharma": { ... }, "C24_metals": { ... }, "C29_auto": { ... } },
      "source": "Cefic analysis based on Eurostat data (sts_inpr_m, 2026)"
    },
    "exports_extra_eu": { ... same structure },
    "imports_extra_eu": { ... },
    "producer_prices": { ... },
    "confidence_indicator": { ... },
    "capacity_utilisation": { ... }
  },
  "editorial_context": {
    "latest_structural_break": "March 2022",
    "notable_events": []
  }
}
```

C'est le contrat entre les fetchers (qui produisent) et le LLM rédacteur (qui consomme). Le `system.md` v2 pourra y faire référence.

## Livrable final

1. `context-prep/data-sources/SOURCES.md` complet selon la structure ci-dessus.
2. Dans une courte section finale `## Next steps`, liste :
   - Les tests de connectivité qui ont échoué ou donné des résultats inattendus (à débugger)
   - Les questions ouvertes qui nécessitent mon arbitrage avant le Livrable 3
   - Ce qui est prêt à être utilisé dès maintenant pour générer des fiches mensuelles réelles

Présente-moi `SOURCES.md` quand c'est prêt. On décidera ensuite si on passe au Livrable 3 sur données réelles (préféré) ou si on doit d'abord débugger les accès Eurostat.
