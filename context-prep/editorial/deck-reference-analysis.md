# Deck reference analysis — `china_us_trade_brief_14042026.pptx`

Source : `context-prep/inputs/china_us_trade_brief_14042026.pptx` (31 slides, Sofia Sacco, Cefic Trade Policy IT, 2026-04-14).

Ce deck porte l'analyse Cefic à un niveau supérieur à ce que couvre `SYNTHESIS.md` (calibré sur Chemical Trends + F&F). Il ajoute du drill-down CN 8-digit, une dualité volume/valeur systématique, et une narration Pareto explicite. L'analyse ci-dessous extrait : arc, patterns nouveaux, types de chart, vocabulaire.

---

## 1. Structure narrative en arc

### Observation

Le deck suit un arc en 3 mouvements :

| Mouvement | Slides | Rôle |
|---|---|---|
| **Macro historique** | 3–8 (6 slides) | Établit le cadre : évolution longue (2010–2025), split NACE, concentration géographique |
| **Focus pays** | 9–28 (20 slides = 4 × 5) | Approfondissement : 2 pays × 2 dimensions × 5 slides par combinaison |
| **Conclusion** | 29–31 (3 slides) | Synthèse structurée sous forme de messages numériques |

Les slides 1–2 sont admin (title / cover). Le focus pays est structurellement homogène : pour chaque combinaison `(pays, dimension ∈ {volumes, values})`, on a **toujours** :

1. Section cover (slide 9, 14, 19, 24)
2. Trade balance line chart 2020–2025 dual-axis (slide 10, 15, 20, 25)
3. NACE 4-digit stacked bars 2020–2025 (slide 11, 16, 21, 26)
4. NACE 4-digit clustered bars avec annotations YoY (slide 12, 17, 22, 27)
5. CN 8-digit drill-down avec pie chart "N products vs rest" (slide 13, 18, 23, 28)

### Template applicable à Iris

Iris monthly n'est pas un deep-dive annuel 2 pays, mais l'arc **macro → focus → conclusion** est transposable directement à une édition mensuelle :

- **Macro Brief** (nouveau, Livrable 5) — titre-diagnostic + 4 KPI cards + bulletin 80–120 mots. Remplit le rôle "cadre établi dès l'ouverture" du deck (slides 3–4) et la concentration géographique (slides 7–8).
- **Sections indicator-level** (existant : output, prices, sales) — rôle des slides macro 3–6 avec leur split NACE.
- **Sections trade enrichies** (Livrable 5) — rôle du focus pays : pour les 3 partenaires clés (US, China, UK), breakdown NACE 4 + drill-down CN 8-digit ciblé. Pas 20 slides par pays : **un seul paragraphe condensé par partenaire** avec le drill-down comme punchline.
- **Key messages en fin d'édition** — optionnel v1.1 : aujourd'hui Iris a un summary en **tête**, pas en queue. Le deck Cefic utilise les deux (lead avec titre-diagnostic, clôture avec key messages). À discuter Phase 3.

---

## 2. Patterns analytiques nouveaux

### 2.1 Pareto implicite (→ nouveau Pattern 19)

**Observation.** Récurrent tout au long du deck, notamment slides 7, 8, 11, 13, 16, 18, 21, 23, 26, 28, 30, 31. Le deck articule les findings autour de **ratios de concentration** :

> *"50% of volumes of imported chemicals are sourced from 5 countries"* (slide 7, title)
> *"70% of the value of imported chemicals is sourced from 5 countries"* (slide 8, title)
> *"5 groups of products (NACE 4-digit) make up over 80% of volumes imported into the EU from China in 2025"* (slide 11, callout)
> *"2 groups of products (NACE 4-digit) make up over 70% of values imported into the EU from China in 2025"* (slide 16, callout)
> *"Half of the increase in imported volumes from China between 2020–2025 is explained by only a limited number of products"* (slide 13, title)
> *"54% of the increase in volumes is caused by increases by 12 8-digit CN codes alone"* (slide 31, key message)

Cette structure est **différente du ranking (Pattern 6)** :
- Pattern 6 énumère un top-N ordonné par valeur absolue.
- Pattern 19 énonce un ratio de concentration — *combien* de l'agrégat provient de *combien peu* d'entités. C'est un jugement structurel sur la fragmentation, pas un classement.

**Template canonique proposé** (à intégrer SYNTHESIS + system §5.6) :

```
With [N] [entities] accounting for [X]% of [total_agregate], the [dimension] is concentrated in [qualifier].
```

Variantes observées :
- *"X% of Y is sourced from N countries"* (concentration géographique)
- *"N groups … make up over X% of …"* (concentration produit)
- *"X% of the increase is caused by N [entities]"* (concentration de la variation — différent de la concentration du stock)

### 2.2 Dualité volume/valeur (→ nouveau Pattern 20)

**Observation.** Chaque slide du focus pays porte un toggle visuel `Volume | Value`, et le deck produit **symétriquement** une variante volume et une variante value pour chaque analyse. Le deck rend explicite la **divergence** entre les deux :

> *"Between 2010 and 2025: +79% change in imported volumes … +167% change in imported values"* (slide 3)
> *"Between 2020 and 2025: −6,95 mln tonnes of change; −27,85 bn EUR of change"* (slide 10, China)
> *"Between 2020 and 2025: −6,3 mln tonnes of change; +36,1 bn EUR of change"* (slide 20, US) ← divergence de signe
> *"Imports from China have increased by +81% in volumes and +182% in value"* (slide 30)
> *"Imports from US have increased by +69% in volumes and +126% in value"* (slide 30)

La dualité n'est pas redondante : elle **porte un insight analytique** (effet prix, glissement vers produits à plus haute valeur ajoutée, compression des marges importateurs).

**Template canonique proposé** :

```
[Entity] [action] by [X]% in volumes and [Y]% in values [between period_start] and [period_end],
[qualifier: "reflecting a shift toward higher-value categories" | "despite lower unit prices" | "driven by X"].
```

Règle d'usage : dans les sections trade, **toujours** citer les deux dimensions. Dans les sections output/prices/sales, mentionner la dualité seulement si la divergence est ≥ 3 points de pourcentage entre volume et value.

### 2.3 Drill-down attribué CN 8-digit (→ nouveau Pattern 21)

**Observation.** Slides 13, 18, 23, 28. Le deck ne se contente pas de breakdowns NACE 4 : il descend au CN 8-digit pour **attribuer une variation totale à un petit ensemble de produits identifiés par code**.

> *"8-digit CN codes:*
> *31022100 — Ammonium sulphate … : +1,3 mln tonnes*
> *29091990 — Acyclic ethers and their halogenated … derivatives (excl. …) : +0,5 mln tonnes — this product was responsible for 28% of the change between the two years*
> *…"* (slide 13)

Caractéristiques :
- Toujours une attribution quantitative (variation absolue + parfois % du delta total).
- Liste tronquée : slide 13 a 12 codes, slide 18 en a 3 seulement, slide 23 en a 4, slide 28 en a 3. Pas de règle fixe — le nombre est dicté par le seuil "50% du delta expliqué".
- Description chimique très longue (parfois > 200 caractères) — acceptable en slide (texte dense), inacceptable en prose éditoriale Iris.

**Template canonique proposé** :

```
[N] CN 8-digit codes account for [X]% of the change in [flow/dimension] between [period_start] and [period_end]:
[code_1] ([short_description_1]), [contribution_1];
[code_2] ([short_description_2]), [contribution_2];
…
```

**Règle de troncation** : description chimique > 40 caractères → garder seulement le chapeau avant la première parenthèse ou la première virgule, suivi de "…". Exemple :
- Slide 13 brut : `29091990 — Acyclic ethers and their halogenated, sulphonated, nitrated or nitrosated derivatives (excl. diethyl ether and tert-butyl ethyl ether …)`
- Iris prose : `29091990 (acyclic ethers and their derivatives, excl. diethyl ether)`

### 2.4 Comparaison de bases temporelles multiples (→ patch system §2)

**Observation.** Le deck mixe **3 fenêtres temporelles** :
- **Longue** : 2010–2025 (slides 3, 4) — baseline structurelle de 15 ans
- **Moyenne** : 2020–2025 (slides 10–28) — fenêtre de 5 ans, dominante du deck
- **Courte/ponctuelle** : 2024–2025 YoY (slides 12, 17, 22, 27 — pourcentages annotés sur les 2025 columns)

Le deck ne s'excuse jamais de cette triple temporalité — il passe d'une fenêtre à l'autre slide par slide sans transition, et le lecteur suit parce que chaque slide explicite sa fenêtre dans le texte ou le titre.

Cela **viole implicitement** une convention non-écrite de `system.md` (calibré sur Chemical Trends, qui utilise surtout YoY + pré-crise). La règle actuelle Pattern 8 ("structural break points use precise dates") suffit pour les événements, pas pour les comparaisons structurelles longues.

**Proposition** : règle §2 patch — *"Jusqu'à 3 fenêtres temporelles distinctes par section sont acceptables (longue-5-à-15-ans, moyenne-YoY, ponctuelle-mois-courant). Chaque fenêtre doit être explicitée : 'between 2020 and 2025', 'year-on-year', 'in February 2026'. Ne jamais empiler plus de 3 fenêtres dans une même section."*

---

## 3. Types de chart et mapping vers Iris

| Chart type (pptx) | Slides | Rôle narratif | Iris existing | Action L5 |
|---|---|---|---|---|
| LINE dual-axis | 3, 10, 15, 20, 25 | Évolution historique ou trade balance volume/value | `index_timeseries.py` (mono-axis) | **Étendre** `index_timeseries` pour dual-axis optionnel, OU créer `trade_balance_dual.py` |
| COLUMN_CLUSTERED (years × categories) | 4, 12, 17, 22, 27 | NACE 4-digit breakdown avec YoY annotations | `yoy_bars.py` (by_country, mono-variable) | **Nouveau** `stacked_bars_nace.py` — clustered par NACE × plusieurs années, annotations YoY sur dernière année |
| COLUMN_STACKED (years × NACE) | 11, 16, 21, 26 | Évolution stacked NACE 4 sur 6 ans | aucun | **Nouveau** `stacked_bars_nace.py` (idem, variante stacked) |
| PIE (donut Pareto) | 13, 18, 23, 28 | Visualisation "N products vs rest" pour drill-down | aucun | **Nouveau** `waterfall_contribution.py` — PIE rejeté (cf §3.2), remplacer par waterfall |
| Maps / country visuals (pictures) | 5, 6, 7, 8 | Split NACE + Pareto géographique | aucun | Hors scope L5 (demande géodonnées, v1.2) |

### 3.1 Waterfall vs pie

Le deck utilise **PIE** pour matérialiser le Pareto au niveau CN. Le prompt L5 propose de le remplacer par **waterfall**, et je suis d'accord pour deux raisons :

- **Pie est absent du corpus Cefic in-depth** (Chemical Trends, Facts & Figures) à l'exception de ce deck de 2026 — c'est-à-dire que le pie n'est pas canonique, il est utilisé ici comme solution d'appoint. Dans le registre analytique Cefic, **waterfall/bridge** est plus standard pour attribuer une variation à ses composants.
- Waterfall porte plus d'information : il montre les contributions individuelles (+1.3 mln tonnes, +0.5 mln tonnes, …) et le total cumulé, là où la pie montre juste "12 products vs rest".

**Décision proposée** : `waterfall_contribution.py` remplace systématiquement le pie dans Iris, avec la **règle d'usage** : waterfall affiché seulement si le top-N explique ≥ 50 % de la variation totale (sinon breakdown tabulaire suffit).

### 3.2 Point de vigilance — décimale

Le deck utilise la **virgule française** comme séparateur décimal (`2,8` / `29,82` / `−6,95`). `system.md` règle 11 impose **point décimal anglais** pour Iris (`2.8` / `29.82`). Les templates de chart L5 doivent respecter cette règle — ne pas copier le format FR de la source.

---

## 4. Formulations narratives à intégrer

### 4.1 À intégrer directement (compatibles avec voix Cefic validée)

| Formulation deck | Usage Iris |
|---|---|
| *"Between [year_a] and [year_b], [action] by [X]% in volumes and [Y]% in values"* | Template Pattern 20 — sections trade |
| *"[N] groups of products … make up over [X]% of [metric] imported … in [year]"* | Template Pattern 19 — concentration produits |
| *"[X]% of [agregate] is sourced from [N] countries"* | Template Pattern 19 — concentration géographique |
| *"Half of the increase in [metric] … is explained by only a limited number of products"* | **Titre-diagnostic** — pattern Pareto appliqué à la variation |
| *"[X]% of the increase in [metric] is caused by increases in [N] 8-digit CN codes"* | Template Pattern 21 — drill-down attribué |
| *"this product was responsible for [X]% of the change"* | Complément Pattern 21 pour l'item le plus contributif |
| *"Spike originated from [compound]"* | Annotation de chart — utilisable en caption ou en aparté |

### 4.2 À adapter

- *"+79% change in imported volumes"* — le deck utilise "change" comme nom général. Iris est plus direct : "volumes increased by 79%". Garder le style Iris.
- *"−12,19 mln tonnes"* — décimale. Iris : `−12.19 million tonnes` ou `−12.2 mln tonnes`.
- *"There is a trend of increase in import volumes in most NACE categories, caused by a limited number of categories of products"* — tournure un peu lourde ("there is a trend of"), préférer la formule plus directe *"Import volumes increased across most NACE categories, driven by a limited set"* (déjà conforme Pattern 1+2 Iris).

### 4.3 À ne PAS intégrer

- La **langue du deck mixe EN et FR numeric** (textes EN, chiffres décimales FR). Iris reste strictement EN + décimale anglaise (cf règle MUST 10 & 11 de system.md).
- Certaines tournures cover slides ("Analysis of imports from China: volumes") sont des titres de section PPT, pas des titres éditoriaux. Iris garde Pattern 4 : titre = déclaration-finding avec figure, pas topic label.

---

## 5. Récapitulatif pour Phase 2

Ce que la Phase 2 doit formaliser à partir de cette analyse :

1. **Pattern 19 — Pareto** : ratio de concentration (stock ou variation). Distinct de Pattern 6 (ranking).
2. **Pattern 20 — Volume/value duality** : phrase-pont systématique en trade, conditionnelle ailleurs.
3. **Pattern 21 — Drill-down CN 8-digit attribué** : liste courte + contribution + règle de troncation.
4. **Patch §2 system.md** : triple temporalité acceptable, ≤ 3 fenêtres par section, toujours explicites.
5. **Patch §5.6–5.8 system.md** : 3 templates canoniques (Pareto, duality, drill-down).

Ce que la Phase 3 doit ajouter côté architecture :
- Macro Brief (nouveau) — titre-diagnostic + KPI cards + bulletin (rôle slides 3–4)
- Trade sections enrichies — Pareto + duality + drill-down sur top 3 partenaires
- 3 nouveaux chart templates — stacked_bars_nace, waterfall_contribution, kpi_card
- Pipeline : étape `build_macro_brief` après `step_process`

---

*Produit par Iris orchestrator — Livrable 5 Phase 1, 2026-04-21.*
