# Prompt Livrable 3 — Stress-test du `system.md` sur données réelles

> À coller dans la session Claude Code en cours.
> `SYNTHESIS.md`, `system.md` et `SOURCES.md` sont validés. On passe à l'étape empirique : le system prompt tient-il la route sur de vraies données ?

---

Go Livrable 3. Objectif : générer 3 sections éditoriales réelles, les auto-évaluer contre `SYNTHESIS.md`, identifier les patches à apporter au `system.md`, itérer une fois.

## Étape 0 — Patches préalables sur `system.md`

Avant tout test, applique ces 5 patches au fichier `context-prep/editorial/system.md`. Ce sont les décisions prises lors de la revue du Livrable 2 + réponses aux questions du Livrable Sources.

### Patch 1 — Clarifier l'interdiction "significantly" (section 3)

Actuellement la section 3 bannit "significantly" mais une note contradictoire laisse penser qu'il est toléré pour >5%. Remplacer la note finale par :

```
**Ban:** "significantly" is banned as an intensifier in Iris. The corpus uses precise
magnitudes (quantified percentages, calibrated verbs from the gradient above).
If tempted to write "significantly decreased", write "decreased by X.X%" instead.
```

### Patch 2 — Contrainte conditionnelle sur "fragmented Europe" (section 5.3)

Actuellement : utilisation systématique après un country breakdown. Remplacer par :

```
### 5.3 Country fragmentation closing # from Pattern 7

After a country-by-country breakdown, close with exactly:

"[These/The] chemical production trends by country show a fragmented Europe."

**Conditional use only.** Apply this closing ONLY when the country data actually
shows heterogeneity:
- At least one country with a positive change AND at least one with a negative change, OR
- Spread between highest and lowest country movement > 5 percentage points.

If all countries move in the same direction with similar magnitudes, do not use
this closing — instead end on the last country figure. Misapplying the phrase
where data is homogeneous would state something false.
```

### Patch 3 — Country breakdown optionnel (section 6.1)

Remplacer le bloc structure par :

```
## 6.1 Chemical Trends-style section (for monthly indicator sections)

[Heading: declarative finding with figure]

[Opening sentence: canonical formula per Template 5.1 if trade, or equivalent
structured opener if output/prices/etc.]

[One-line benchmark: vs pre-crisis or vs competitor region]

[IF breakdown data available in data block:]
  [Sub-sector or country breakdown using Template 5.2, 2-3 sentences]
  [IF country breakdown AND heterogeneity test passes: Template 5.3 closing]

{{chart:[chart_id]}}
Source: Cefic analysis based on Eurostat data ([year][, note])
```

Le breakdown est conditionnel à la présence de données. Pas de breakdown inventé.

### Patch 4 — Règle de révisions dans section 7

Ajouter une ligne finale à la table de la section 7 :

```
| Past-edition revision | Iris never re-builds past editions. If Eurostat revises
a figure used in a previous edition, mention the revision in the current edition:
"Revised from €X.X bn published in the [Month] edition, following Eurostat data
revision." The past edition remains archived as-published. |
```

### Patch 5 — Format numérique et unités (nouvelle section 1, règle 11 et 12)

Ajouter en section 1 :

```
11. **Decimal format is English.** €25.0 bn (point decimal), not €25,0 bn (comma).
Thousand separator: comma (€1,250 million) or space. # from Style Guide §14

12. **Unit conventions (non-negotiable):**
  - Trade values: `€ bn` (e.g. "€148.6 bn"), not "billion euros" or "€ billion"
  - Percentage changes: `%` (e.g. "decreased by 2.3%"), not "percent"
  - Percentage point differences: `pp` (e.g. "down 1.2 pp"), not "percentage points"
  - Index values: dimensionless (e.g. "98.4"), with baseline in caption when first introduced
  - Capacity utilisation: `%` on the value itself (e.g. "74.0%")
  # from Style Guide §14.2
```

### Patch 6 — Note sur Cefic segments vs CN chapters

Ajouter en section 2, comme règle 7 :

```
7. **Segment labels follow the data block.** If the data block exposes indicators
by CN chapter (e.g. "CN 29", "CN 38"), refer to them as such. Do not reconstruct
Cefic segment groupings (petrochemicals, specialty, consumer, polymers) unless
the data block explicitly provides them. In v1, most indicators will be reported
by CN chapter; Cefic segments will come in v1.1 when the Comext ETL feeds Iris
directly.
```

### Patch 7 — Règle GDP trimestriel

En section 7, ajouter à la ligne "Latency" un exemple explicite :

```
Example: when referencing GDP in a monthly report, use the most recent quarter
available with the latency formula: "latest available: Q4 2025". Do not reference
annual GDP in a monthly edition.
```

**Présente-moi le `system.md` patché avant de passer à l'étape 1.** Je veux le valider d'un coup d'œil avant que tu génères quoi que ce soit.

---

## Étape 1 — Trois fiches de test sur données réelles

Une fois le `system.md` patché validé, génère 3 fiches d'input réelles dans `context-prep/editorial/test-inputs/`.

### Fiche 1 — Section Output (production)
- **Source :** API Eurostat `sts_inpr_m` (fonctionnelle per SOURCES.md)
- **Données réelles** : NACE C20, février 2026 (dernière période disponible), avec :
  - Valeur courante + YoY
  - Benchmark pre-crisis (moyenne 2014-2019, à calculer)
  - Breakdown C20 vs C21 (pharma) vs C24 (métaux) vs C29 (auto)
  - Breakdown par pays (top 7 chimistes EU : DE, FR, NL, IT, ES, BE, PL)
- **Format :** JSON exactement conforme à `system.md` section 10 et `SOURCES.md` section 7. Si les deux schémas divergent encore, réconcilie-les en faveur de celui de `SOURCES.md` et mets à jour `system.md` en conséquence.

### Fiche 2 — Section Producer Prices
- **Source :** API Eurostat `sts_inppd_m`
- **Données réelles** : NACE C20, février 2026
- YoY, benchmark sector-wide (total industry C), breakdown par pays

### Fiche 3 — Section Turnover
- **Source :** API Eurostat `sts_intv_m`
- **Données réelles** : NACE C20, janvier 2026 (latence plus forte, per SOURCES.md)
- YoY, benchmark C, breakdown sous-secteurs NACE C2011/C2014/C2015/C2016/C2020 si dispo (sinon chapitre C20 seul)
- **Cas intéressant** : la latence est d'un mois de plus que les deux autres → teste la règle de latency (template "latest available: [period]")

**Pour chaque fiche :**
- Extraire les données via appel API réel (pas inventer)
- Sauvegarder en JSON dans `test-inputs/fiche_N_[indicator].json`
- Sauvegarder aussi en markdown lisible dans `test-inputs/fiche_N_[indicator].md` (ce qui permet de relire les chiffres hors contexte technique)

## Étape 2 — Génération des 3 sections

Pour chacune des 3 fiches, appelle l'API Anthropic avec :
- **System prompt :** le `system.md` patché, chargé intégralement
- **User message :** le JSON de la fiche
- **Model :** `claude-opus-4-5` ou équivalent disponible. **Sonnet suffit pour ce test.**
- **Temperature :** 0.3 (prose structurée, peu de créativité)

Sauve les 3 sorties dans `context-prep/editorial/test-outputs/fiche_N_[indicator].md`.

## Étape 3 — Auto-évaluation rigoureuse

Pour chacune des 3 sorties, produis un fichier `test-outputs/EVAL_fiche_N.md` structuré comme suit :

### 3.1 Checklist mécanique (binaire)

Passe chaque output contre les 10 points de la self-check section 11 du `system.md` :
- ✅ / ❌ pour chaque point
- Si ❌, cite le passage fautif en blockquote

### 3.2 Checklist de voix (qualitatif)

Pour chaque output, évalue contre les patterns SYNTHESIS.md les plus importants :

| Pattern | Observation | Verdict |
|---|---|---|
| Pattern 1 (chiffre d'abord) | ... | ✅/⚠️/❌ |
| Pattern 2 (dual-period) | ... | ... |
| Pattern 3 (trade formula) ou équivalent | ... | ... |
| Pattern 4 (heading as finding) | ... | ... |
| Pattern 5 (verbes calibrés) | ... | ... |
| Pattern 14 (no conclusion) | ... | ... |
| Pattern 15 (densité chiffrée) | compte réel : N chiffres / M phrases | ✅ si ≥ 0.5 |
| Pattern 16 (longueur phrase) | moyenne réelle : X mots | ✅ si ≤ 25 |
| Pattern 17 (connecteurs) | liste des connecteurs bannis trouvés | ✅ si 0 |

### 3.3 Tests spécifiques au patches

- Patch 2 (fragmented Europe conditional) : le closing est-il utilisé à bon escient compte tenu des données ?
- Patch 3 (breakdown optionnel) : le breakdown est-il présent et cohérent avec la fiche ?
- Patch 5 (format unités) : les `€ bn`, `%`, `pp` sont-ils conformes ?

### 3.4 Diagnostic et patches proposés

À la fin de chaque EVAL, propose **au maximum 3 patches** au `system.md` pour corriger les dérives observées. Patches formulés comme des additions/modifications précises, pas des vagues "améliorer la voix".

## Étape 4 — Synthèse et itération

Une fois les 3 EVAL produits, crée `test-outputs/SUMMARY.md` qui :

1. **Liste les patterns qui tiennent** (sortie Iris conforme au corpus)
2. **Liste les patterns qui dérivent** (fréquence des problèmes, regroupés par type)
3. **Consolide les patches proposés** des 3 EVAL en une liste priorisée (top 3-5)
4. **Pose les questions éditoriales restantes** qui nécessitent mon arbitrage humain (pas des questions techniques)

## Étape 5 — Itération unique

Applique les top 3-5 patches au `system.md`. Re-génère **une seule** des 3 sections (choisis celle avec le plus de dérives initiales). Sauve la nouvelle version sous `test-outputs/fiche_N_[indicator]_v2.md`. Compare v1 et v2 dans `test-outputs/ITERATION_DIFF.md` : qu'est-ce qui s'améliore, qu'est-ce qui régresse, qu'est-ce qui reste problématique.

## Contraintes transversales

- **Aucune donnée inventée.** Si l'API Eurostat refuse un paramètre, note l'échec et bascule sur un indicateur alternatif. Mieux vaut 2 fiches réelles que 3 fiches dont 1 fictive.
- **Aucune modification de `SYNTHESIS.md`.**
- **Pas de structure Iris définitive.** Tout reste dans `context-prep/`.
- **Commit git intermédiaire en local** après chaque étape majeure (patches système, fiches, outputs, eval, itération) pour pouvoir rollback. Pas de push.
- **Si l'API Anthropic échoue (clé manquante, rate limit) :** fais tout le travail jusqu'à l'étape 1 + patches, puis stoppe proprement et dis-le. Ne simule pas une sortie LLM.

## Livrable final

Présente-moi, dans cet ordre :

1. Le `system.md` patché (étape 0)
2. Les 3 fiches `test-inputs/fiche_N_*.json` (résumé suffisant, pas besoin de tout afficher)
3. Les 3 outputs `test-outputs/fiche_N_*.md` en intégralité
4. Les 3 `EVAL_fiche_N.md` en intégralité
5. Le `SUMMARY.md`
6. La version v2 de la fiche re-générée + le `ITERATION_DIFF.md`

Ensuite on décide si le system prompt est prod-ready ou s'il faut une deuxième itération.

Go.
