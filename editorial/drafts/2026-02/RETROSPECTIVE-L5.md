# RETROSPECTIVE L5 — Iris v0.2.0 (February 2026 edition)

Date : 2026-04-21. Pipeline version : 0.2.0. Target month : 2026-02 (Eurostat-latest, Comext-latest).

Ce retour d'expérience couvre la première édition complète produite avec le pipeline enrichi du Livrable 5 : macro brief, dualité volume/valeur, drill-down CN 8-digit, chart templates nouveaux. Il compare la sortie v0.2.0 à la baseline v1 (édition `cd93ec7`) et liste les dettes techniques résiduelles.

---

## 1. Ce qui fonctionne

### 1.1 Pipeline end-to-end

Le run complet `python pipelines/monthly_run.py --month 2026-02 --dry-run --force` est passé en **~45 s** :

- FETCH : 5 sources Eurostat + Comext parquet (193 MB) + SubstanceId.csv. ~15 s.
- PROCESS : 5 fiches indicateur + 1 fiche macro_brief. <2 s.
- DRAFT : 5 sections, 100 % Sonnet, temps cumulé ~25 s.
- MACRO BRIEF : fallback Opus déclenché 1 fois sur 2026-02 (Sonnet dépassait 120 mots, Opus OK à 116 mots).
- VISUALIZE : **10 charts SVG** (6 indicator + 3 KPI cards + 1 waterfall). <3 s.
- BUILD : MDX assemblé. <1 s.

Aucune exception, aucun retry API.

### 1.2 Voix Cefic préservée

Les 5 MUST rules de `system.md` §1 restent respectées sur les 5 sections rédigées. Les patterns nouveaux (19, 20, 21) s'intègrent sans casser les anciens :

- **Pattern 3 (formule trade canonique)** : *"EU27 chemical exports amounted to €34.5 bn in the first two months of 2026, down by €25.1 bn compared to 2025."* ✓
- **Pattern 6 (ranking)** : *"With €4.4 bn, China is the primary source of imports … followed by the United States (€3.7 bn) and Switzerland (€1.9 bn)."* ✓
- **Pattern 7 (fragmented Europe)** : appliqué conditionnellement, verbatim identique. ✓
- **Pattern 11 (source line)** : *"Source: Cefic analysis based on Eurostat data (2026)"* ✓

### 1.3 Patterns 19-21 appliqués à la prose

**Pattern 19 (Pareto)** — macro brief :
> *"With 5 export partners accounting for 50.0% of trade value, concentration remained high despite the United States experiencing the steepest decline at 72.5% …"*

Seuil 50 % exactement franchi → le flag `concentration_pareto` est bien positionné et la formule canonique s'applique.

**Pattern 20 (dualité volume/valeur)** — trade_exports et trade_imports :
> *"EU27 chemical exports decreased by 42.1% in value and 17.4% in volume in comparison to the same period in 2025."*
> *"EU27 chemical imports fell by 18.5% in volume and 12.0% in value between January and February 2025 and 2026, reflecting lower average unit prices."*

Les deux sections trade citent systématiquement les deux dimensions (règle trade-always). Le macro brief reprend la formulation au niveau sectoriel.

**Pattern 21 (drill-down CN 8-digit)** — trade_imports :
> *"With 5 CN 8-digit codes accounting for 64.0% of the change in Chinese imports between February 2021 and February 2026: 29371900 (polypeptide hormones), +€0.9 bn; 29339980 (heterocyclic compounds with nitrogen…), +€0.6 bn; 29335995 (heterocyclic compounds with nitrogen…), +€0.5 bn; 29349990 (nucleic acids and their salts), +€0.1 bn; 24041200 (products containing nicotine…), +€0.1 bn."*

Déclenché sur CN (pas US cette fois, inverse de 2025-12), coverage 64 %. La règle de troncation à 40 caractères s'applique correctement (`heterocyclic compounds with nitrogen…`).

### 1.4 Triple temporalité

Le macro brief mélange 3 fenêtres :
- *"in the first two months of 2026"* (pointwise) — ok
- *"year-on-year"* implicite via *"declining by 3.9% year-on-year"* — ok
- *"pre-crisis levels (2014–2019 average)"* — long window — ok

Les sections respectent aussi §2 rule 8 (≤ 3 fenêtres par section).

### 1.5 Charts nouveaux

- **3 KPI cards** (`macro_kpi_output.svg`, `macro_kpi_prices.svg`, `macro_kpi_trade_balance.svg`) : rendus en 280×160 px, delta coloré, pas de sparkline (non-nécessaire pour 2026-02 car pas de série mensuelle dans les fiches).
- **1 waterfall** (`trade_imports_waterfall_cn8.svg`) : drill-down Chine, 5 codes CN + "Other products" + total. 71 KB.

Toutes les couleurs viennent de `charts/style.py` — aucune constante inline.

---

## 2. Comparaison v1 (cd93ec7) vs v0.2.0

| Dimension | v1 (2026-04-18) | v0.2.0 (2026-04-21) |
|---|---|---|
| **Ouverture** | Summary 4-bullets, sans chiffre saillant dans le titre | Macro brief : titre-diagnostic avec figure, paragraphe 116 mots, 3 KPI cards rendues |
| **Sections produites** | 4 (output, prices, sales — pas de trade, Comext stub) | **5** (output, prices, sales, trade_exports, trade_imports) |
| **Lignes edition.md** | 60 | 86 |
| **Charts** | 6 (2 par section indicator) | **10** (6 indicator + 3 KPI + 1 waterfall) |
| **Patterns mobilisés** | 3, 6, 7, 11 | 3, 6, 7, 11, **19, 20, 21** |
| **Fenêtres temporelles** | YoY + YTD + pre-crisis | YoY + YTD + pre-crisis + **five-year + pointwise** |
| **Drill-down** | aucun | Pattern 21 sur imports Chine, 64 % coverage |
| **Pipeline version** | 0.1.0 | **0.2.0** |
| **Temps de run** | ~30 s | ~45 s (+50 %) |

La v0.2.0 ouvre par un diagnostic chiffré, ferme chaque section trade par un drill-down produit, et porte le toggle volume/valeur comme une règle systématique. La v1 restait sur une narration d'indicateurs monoblocs.

---

## 3. Dettes techniques identifiées (non bloquantes)

### 3.1 Chart stacked_bars_nace non rendu faute de données

Le dispatcher `trade_*_nace_stacked` n'est pas peuplé dans `CHART_DISPATCHERS` car `trade.json` n'expose pas encore `by_year_by_nace` (agrégation NACE 4 × année sur la fenêtre 5 ans). Le template `charts/templates/stacked_bars_nace.py` est prêt mais inutilisé.

**Fix prévu v0.2.1** : ajouter un helper `_nace_yearly_series(flow_df, cn_to_nace)` dans `comext.py`, émettre `by_year_by_nace` dans `trade.json`, wire dans `CHART_DISPATCHERS`. Travail estimé : 1 commit, ~40 lignes.

### 3.2 Waterfall : un seul partner par flow

Le render prend uniquement le **premier** key partner avec un `drill_down`. Pour le deck Cefic complet (4 waterfalls : US volumes, US values, CN volumes, CN values), il faudrait en produire jusqu'à 6 (3 partenaires × 2 dimensions) ou itérer les flows. Pour v0.2.0, un seul suffit — le reste est dans la prose.

**Amélioration v0.3** : rendre un SVG waterfall par `(flow, key_partner)` dès que la concentration est ≥ 50 %.

### 3.3 4e KPI absente

`capacity.json` n'est pas produit dans v0.2.0 — aucune fonction `fetch_capacity()` dans `eurostat.py`. Le macro brief ferme donc sur 3 KPI cards au lieu de 4. C'est conforme à la **Décision L5.1** (fallback silencieux), mais l'édition serait plus forte avec la 4e.

**Fix v0.3** : écrire `fetch_capacity()` ciblant `ei_bsin_m_r2` ou `ei_bsci_q_r2`. Parser le résultat dans un fiche `capacity.json`. Travail estimé : 1 commit, ~60 lignes.

### 3.4 Fallback Opus prévisible

Sur 2026-02, Sonnet a produit 129 mots au premier essai (bordure haute 120). Opus a repris à 116. Le coût par édition augmente légèrement (~$0.80 au lieu de $0.15). C'est acceptable en mensuel mais suggère :
- Soit relâcher le plafond à 130 (marge de sécurité pour Sonnet).
- Soit injecter une contrainte renforcée dans `macro_brief.md` : *"Count your words — target ≤ 115 to leave margin."*

**Décision reportée** — attendre 3 éditions pour voir si c'est systématique.

### 3.5 Labels CN tronqués parfois identiques

Deux codes CN (29339980, 29335995) produisent le même label tronqué : *"heterocyclic compounds with nitrogen…"*. Visuellement moche dans la prose : *"29339980 (heterocyclic compounds with nitrogen…), +€0.6 bn; 29335995 (heterocyclic compounds with nitrogen…), +€0.5 bn"*. Le lecteur ne peut plus les distinguer.

**Fix v0.3** : si deux labels tronqués sont identiques, garder le code CN sans label, ou remonter le label suivant l'arbre product_dim (`heading` parent).

### 3.6 "These chemical exports trends by country show a fragmented Europe" sur trade

La section trade_exports ferme sur *"These chemical export trends by country show a fragmented Europe."* Or c'est une ventilation **par partenaire**, pas par pays EU. C'est une anomalie héritée du Pattern 7 qui s'active aussi sur les sections trade. Mentionné dans `deck-reference-analysis.md` §1, pas encore patché.

**Fix v0.3** : ajouter dans `system.md` §5.3 une condition explicite : Pattern 7 s'applique **uniquement** sur ventilations par pays EU (DE, FR, IT, …), pas sur partenaires commerciaux extra-EU.

### 3.7 Font warning "Inter" non critique mais visible

Matplotlib logge `WARNING: findfont: Font family 'Inter' not found.` des dizaines de fois par run. L'OS Yaghi n'a pas Inter installé — fallback sur DejaVu Sans silencieux. Pas bloquant pour Azure (les SVG embarquent les glyphes), mais pollue les logs.

**Fix trivial** : `apt-get install fonts-inter` ou bien remplacer Inter par Arial dans `FONT_STACK` (Arial est présent partout).

---

## 4. Ce qu'il reste à faire avant publication

- **Review éditoriale humaine** sur l'édition 2026-02 — Moncef Hadhri en PR.
- **Déploiement Azure SWA** validé (workflow `2325657` OK) — prochain push triggera le build automatiquement.
- **Régénération mensuelle via cron** — mardi 28 avril 09:00 CEST (cf. crontab). Le premier run "vrai" produira soit 2026-02 (si Eurostat freeze) soit 2026-03 (si publication entre temps).

---

## 5. Validation des 4 décisions ouvertes L5

| Décision | Proposition Phase 3 | Appliqué dans v0.2.0 | Verdict |
|---|---|---|---|
| L5.1 — 4e KPI | Variable, capacity → confidence → omission | Omission (capacity non implémentée) | ✓ (dette §3.3 à résorber v0.3) |
| L5.2 — Drill-down auto/seuillé | Seuillé à 50 % coverage sur key_partners | 50 % threshold respecté | ✓ |
| L5.3 — Rétro-compat v1 | On n'y touche pas | `pipeline_version: "0.2.0"` dans le manifest ; v1 reste à "0.1.0" via fallback summary | ✓ |
| L5.4 — Position drill-down | Inline dans section trade | Drill-down inline dans trade_imports, paragraphe entre by_partner et by_chapter | ✓ |

Les 4 décisions sont ratifiées par l'implémentation. Pas de revirement nécessaire.

---

## 6. Prochains jalons

- **v0.2.1** (fix du stacked_bars NACE) — 1 commit.
- **v0.3** (capacity fetcher + waterfall multi-partner + labels CN dédupliqués + patch Pattern 7) — 4 commits.
- **v1.0** (linter éditorial automatique + prompts spécialisés par section) — attendu après 3 éditions dry-run humaines revues par Dr Hadhri.

Prochaine édition attendue automatiquement : **2026-04-28 09:00 CEST** via cron. Cible `$(date -d "-2 months" +%Y-%m)` = 2026-02 au moment du run (ou 2026-03 si Eurostat a publié d'ici là).

---

*Produit par Iris orchestrator — Livrable 5 Phase 5, 2026-04-21.*
