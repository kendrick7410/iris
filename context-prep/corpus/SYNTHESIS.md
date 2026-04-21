# SYNTHESIS — Patterns transversaux de la voix Cefic Economic Outlook

Extrait empiriquement de 6 publications : 4 chapitres Facts & Figures 2025 (Profile, Trade Development, Growth & Competitiveness, Energy Consumption) + 2 Chemical Trends Reports (Q3 2025, Q4 2025).

---

## 1. Le chiffre d'abord, l'interprétation après

Chaque affirmation analytique est ancrée sur un chiffre précis. L'interprétation ne vient qu'après, et reste descriptive. Jamais de claim sans donnée.

- *"The EU27 chemicals trade surplus amounted to €25.0 bn in the first eight months of 2025, down by €6.6 bn compared to 2024."* (CT Q3)
- *"At 74.0% capacity utilisation in the EU27 chemical sector remains a key concern."* (F&F Growth)

**Implication pour le system prompt :** Interdire toute phrase analytique sans chiffre sourcé. Le chiffre n'est pas une illustration — c'est l'ossature.

---

## 2. Le dual-period comparison est systématique

Aucun chiffre n'est présenté seul. Il est toujours adossé à au moins une comparaison : YoY, vs pre-crisis (2014-2019), vs région concurrente, ou vs sous-secteur.

- *"EU27 chemical exports decreased by 2.3% in 2025 in comparison to the same period in 2024."* (CT Q3)
- *"EU27 chemicals operate at 9.5% below pre-crisis capacity (2014–2019)."* (F&F Growth)

**Implication :** Imposer au moins un benchmark par chiffre. Un chiffre isolé = un draft incomplet.

---

## 3. La formule "From [window], [indicator] [verb] by [%]... amounting to €X bn, [direction] by €Y bn compared to [year]"

C'est la phrase canonique du Chemical Trends. Elle apparaît dans chaque section trade, avec une régularité mécanique. Structure : fenêtre temporelle → indicateur → verbe directionnel → % → montant absolu → delta absolu vs N-1.

- *"From January to August 2025, EU27 chemical exports decreased by 2.3% in 2025 in comparison to the same period in 2024. The EU27 chemicals exports amounted to €148.6 bn in the first eight months of 2025, down by €3.5 bn compared to 2024."* (CT Q3)
- *"From January to October 2025, EU27 chemical exports decreased by 3.8% in 2025 in comparison to the same period in 2024, reaching €183.2 bn in the first ten months of 2025, down by €7.2 bn compared to 2024."* (CT Q4)

**Implication :** Fournir cette formule comme template explicite dans le system prompt. C'est la signature mécanique du registre.

---

## 4. Le heading-as-finding (pas heading-as-topic)

Les titres de section ne nomment jamais le sujet seul. Ils énoncent le constat. Un lecteur qui ne lit que les titres comprend le rapport.

- *"EU27 chemical capacity utilisation remains steadily low (74%)"* — pas "Capacity utilisation"
- *"January to August 2025: EU27 chemical exports value below 2024 levels"* — pas "Exports"
- *"Weak demand continues to weigh on EU27 chemical production"* — pas "Demand"

**Implication :** Imposer la règle : un heading est une phrase déclarative complète avec, idéalement, un chiffre.

---

## 5. Le vocabulaire directionnel est calibré, pas interchangeable

Le corpus utilise un gradient de verbes soigneusement calibré selon la magnitude du mouvement :

- Mouvement faible : *"slightly decreased"*, *"remained stable"*, *"edged up"*, *"modest improvement"*
- Mouvement moyen : *"decreased by"*, *"declined"*, *"grew"*, *"rose"*
- Mouvement fort : *"plummeted"*, *"declined sharply"*, *"fell sharply"*, *"more than tripled"*

Exemples calibrés côte à côte dans le même rapport :
- *"rose slightly in December 2025"* vs *"the confidence indicator fell sharply in France (-6.1)"* (CT Q4)
- *"slightly decreased in 2024 vs 2023"* vs *"dropped sharply in a growing global market"* (F&F Profile)

**Implication :** Fournir le gradient de verbes et l'associer à des seuils (ex: <1% = "slightly", 1-5% = neutre, >5% = "sharply"). Les LLM tendent à utiliser "significantly" partout.

---

## 6. La structure récurrente "With €X bn, [entity] is the primary/largest..."

Pour les ventilations (par pays, par sous-secteur), le corpus utilise toujours la même tournure inversée : montant en tête, puis rang.

- *"With €28.3 bn, USA is the primary source of exports of the EU27 area for chemicals, followed by the UK (€17.0 bn) and China (€11.6 bn)."* (CT Q3)
- *"With €48.1 bn, petrochemicals is the largest import sector followed by specialty chemicals (€29.3 bn) and polymers (€21.0 bn)."* (CT Q3)

**Implication :** Template à injecter directement. La structure inversée (montant → entité → rang) n'est pas naturelle pour un LLM.

---

## 7. "A fragmented Europe" — la phrase de clôture des sections pays

Après chaque ventilation par pays, le corpus clôt systématiquement par un constat d'hétérogénéité.

- *"Chemical production trends by country show a fragmented Europe."* (CT Q3)
- *"These chemical production trends by country show a fragmented Europe."* (CT Q4)

**Implication :** C'est une phrase-signal. Elle apparaît mot pour mot dans les deux rapports. Le system prompt doit la référencer comme closing pattern standard.

---

## 8. Le "since March 2022" comme point de rupture narratif

Mars 2022 (invasion de l'Ukraine / crise énergétique) est systématiquement cité comme le point d'inflexion structurel. Ce n'est pas "la crise" ou "la pandémie" — c'est mars 2022.

- *"The EU27 chemicals business environment has been facing a limited demand since March 2022."* (CT Q3)
- *"As we approach four years since the onset of the recession (March 2026), the persistently low level of business confidence remains a core concern"* (CT Q4)

**Implication :** Imposer une règle générale : ancrer les ruptures structurelles sur une **date précise (mois + année)**, jamais sur une période floue ("post-pandemic", "recent years", "after the crisis"). La date de référence actuelle est **mars 2022** (crise énergétique post-invasion Ukraine). Si un nouveau point d'inflexion émerge (ex: tarifs US mars 2025), le traiter de la même façon : date précise, pas périphrase.

---

## 9. Le contraste specialty vs petrochemicals comme fil rouge

Le corpus distingue systématiquement la santé du secteur chimique selon le segment. Les specialty et consumer chemicals sont résilientes (excédent commercial). Les petrochemicals et basic inorganics sont en crise (déficit, surcapacité, concurrence chinoise).

- *"In spite of an overall trade surplus, with €19.2 bn, petrochemicals is generating the largest trade deficit [...] In contrast, specialty chemicals and consumers chemicals continue to generate a trade surplus of more than €24 bn each"* (CT Q4)
- *"Specialty chemicals dominates export & petrochemicals dominates import in 2024"* (F&F Trade)

**Implication :** Ne jamais traiter "la chimie" comme un bloc homogène. Toujours expliciter la divergence specialty/petrochemicals quand les données le permettent.

---

## 10. La troisième personne institutionnelle — sauf quand le ton durcit

Le registre standard est strictement à la 3e personne : "the sector", "the EU27 chemical industry", "the industry". Jamais de "we" dans le corps.

Mais le Q4 2025 introduit un glissement subtil : *"We should also highlight that..."* (p.8). Et le Q3 utilise *"the recipes that worked in the past seem to have reached their limits"* — une métaphore inhabituelle. Ces écarts sont rares et signalent un durcissement éditorial volontaire.

- Standard : *"The output of the EU27 chemical industry remains 10% below the pre-crisis levels"*
- Glissement Q4 : *"We should also highlight that the extra-EU27 chemical export values have increased for the second consecutive month"*

**Implication :** Imposer la 3e personne stricte dans le system prompt. Le "we" ponctuel du Q4 2025 ("We should also highlight...") est un choix éditorial de l'auteur humain — le Chief Economist qui s'autorise un apartée analytique. Un LLM qui utilise "we" produit un effet différent : il simule une personnalité institutionnelle qu'il n'a pas. **Règle Iris : 3e personne stricte, zéro "we".** Si un point mérite un soulignement fort, utiliser *"It is also worth noting that..."* ou simplement une phrase déclarative directe. Le risque d'une divergence détectable avec le rapport humain est faible : le "we" n'apparaît qu'une fois sur deux rapports entiers, et sa suppression ne sera pas remarquée.

---

## 11. La source-line est invariable et fait partie du texte

Chaque graphique porte une ligne de source formatée de façon rigide. Ce n'est pas un pied de page — c'est du contenu.

- *"Source: Cefic analysis based on Eurostat data (2025)"*
- *"Source: Cefic analysis based on Eurostat data (2025, NACE code 20)"*
- *"Source: Cefic analysis based on Eurostat data, *Jan-Sep 2025"*

**Implication :** Le system prompt doit imposer cette ligne verbatim. Jamais "Source: Eurostat" seul, jamais "Data from Eurostat".

---

## 12. Le summary du Chemical Trends suit un arc en 4 bullets

Chaque rapport commence par un diagnostic-titre + 4 bullets qui suivent le même arc :
1. Situation actuelle (demande, compétitivité)
2. Pression concurrentielle (Chine, commerce)
3. Driver structurel (énergie, régulation)
4. Indicateur avancé (investissement, fermetures, désindustrialisation)

- Q3 : "EU27 chemical business is struggling" → 4 bullets
- Q4 : "The EU27 chemical industry is facing a tough reality" → 4 bullets

**Implication :** Imposer cet arc comme template pour les résumés. L'ordre des bullets n'est pas arbitraire.

---

## 13. L'ouverture F&F suit un schéma à 4 temps

Les chapitres Facts & Figures ouvrent avec un pattern reconnaissable :
1. **Fait d'ancrage** avec chiffre-phare (taille, rôle)
2. **Composition structurelle** (sous-secteurs, géographie, clients)
3. **Benchmark** vs pre-crisis / concurrent / historique
4. **Diagnostic actuel** ou nuance

- Profile : €635 Mds + 1.2M emplois → sous-secteurs → Chine 46% vs Europe 13% → déclin 8 pp
- Growth : compétitivité < pre-crisis → pétro vs specialty → gap gaz 3x → confiance en baisse depuis mars 2022
- Energy : industrie energy-intensive → 25-50% gaz feedstock → gap gaz 3x → 40% efficacité depuis 1990

**Implication :** Encoder ce schéma comme un template d'ouverture dans le system prompt.

---

## 14. L'absence de clôture formelle

Ni les chapitres F&F ni les Chemical Trends ne comportent de paragraphe de conclusion, de résumé, ou de "takeaway". Le dernier graphique / la dernière section se termine simplement par le dernier constat chiffré. L'absence de clôture est un choix éditorial : les données parlent d'elles-mêmes.

- F&F Profile se termine par : *"Global chemical sales 2024 are 3.6 times higher than in 2004"*
- CT Q4 se termine par : *"Net, trade deficit for EU27 chemicals more than tripled from 2024 to 2025 (Jan-Oct)."*

**Implication :** Le system prompt doit interdire les conclusions de type "In summary..." ou "Overall, the data suggests..." que les LLM produisent naturellement. Finir sur le dernier chiffre, point.

---

## 15. La densité chiffrée : une donnée toutes les 1-2 phrases

En comptant les chiffres dans les sections in-depth du Chemical Trends, on observe en moyenne un chiffre (%, €, mt, index) toutes les 1 à 2 phrases. Les paragraphes sans chiffre sont rarissimes — et quand ils existent, ce sont des transitions contextuelles ("The high level of uncertainty is impacting deeply the European business community").

- Section exports Q3 (2 paragraphes, 8 chiffres) : €148.6 bn, €3.5 bn, 2.3%, €28.3 bn, €17.0 bn, €11.6 bn, €49.8 bn, €33.1 bn
- Section confidence Q4 (3 paragraphes, 8 chiffres) : -6.1, -4.9, -3.9, -1.2, -0.9, -0.7, March 2022, four years

**Implication :** Imposer un ratio minimum de densité chiffrée. Si un paragraphe analytique ne contient aucun chiffre, c'est probablement du remplissage LLM.

---

## 16. Longueur et structure de phrase : plus court que ce qu'un LLM produit

Mesuré sur 8 paragraphes du corpus (4 CT + 4 F&F, 39 phrases au total) :

- **Moyenne : 19.1 mots/phrase**
- **Médiane : 20.0 mots/phrase**
- **Distribution : 38% courtes (<=15 mots), 41% moyennes (16-25), 21% longues (26-35), 0% très longues (>35)**
- **Ratio simple/subordonnée : 59% simples / 41% avec subordonnée**

Le registre est **plus court et plus simple que ce qu'un LLM produit spontanément**. Les phrases courtes (<15 mots) sont fréquentes et servent de ponctuations analytiques :

- *"Chemicals are therefore highly impacted by gas prices."* (8 mots — F&F Energy)
- *"Chemical companies are facing a very difficult global economic context."* (10 mots — CT Q4)
- *"Uncertainty continues to penalise investment, and forecasts for 2026 are modest."* (11 mots — CT Q4)

Les phrases longues (>25 mots) portent toujours une ventilation par pays ou sous-secteur, pas de la prose abstraite :

- *"With €28.3 bn, USA is the primary source of exports of the EU27 area for chemicals, followed by the UK (€17.0 bn) and China (€11.6 bn)."* (26 mots — CT Q3)

Aucune phrase ne dépasse 35 mots dans l'échantillon mesuré.

**Implication :** Imposer dans le system prompt : phrases de 15-25 mots en moyenne. Les phrases >30 mots ne sont acceptables que si elles portent une liste de données (pays, sous-secteurs). Interdire les phrases >35 mots. Les LLM tendent vers 25-35 mots avec 2-3 subordonnées imbriquées — c'est hors registre.

---

## 17. Connecteurs logiques : un inventaire fermé

### Connecteurs observés (par fréquence décroissante)

**Dominants (3+ occurrences) :**
- *"however"* (3x) — contraste dominant, toujours en début de phrase
- *"compared to"* / *"in comparison to"* (omniprésent) — comparaison temporelle, pas un connecteur logique classique mais la cheville du registre

**Réguliers (2x) :**
- *"driven by"* — cause, toujours en fin de phrase ou apposition
- *"while"* — contraste secondaire, en milieu de phrase

**Ponctuels (1x chacun) :**
- Contraste : *"whereas"*, *"by contrast"*, *"in contrast"*, *"apart from"*
- Cause : *"due to"*, *"given"*, *"as a result"*, *"therefore"*
- Conséquence : *"leaving"*, *"keeping"*, *"placing"*, *"reflecting"* (participes présents causaux — signature du registre)
- Exemple : *"for instance"*, *"particularly"*
- Concession : *"in spite of"*, *"unfortunately"*, *"as expected"*
- Mise en relief : *"importantly"* (1 seule occurrence, dans le summary Q4)

### Liste noire — connecteurs LLM absents du corpus

Vérifiés contre le texte intégral des 6 publications :

| Absent | Remplacement Cefic |
|---|---|
| *furthermore* | *in addition* (rare aussi) ou simple juxtaposition |
| *moreover* | absent — le corpus juxtapose sans escalade |
| *additionally* | absent |
| *in conclusion* | absent — pas de conclusion formelle (cf. Pattern 14) |
| *notably* | absent — utiliser *"particularly"* |
| *it is worth noting* | absent (mais proposé comme alternative au "we" — Pattern 10) |
| *it should be noted* | absent |
| *in summary* / *to summarize* | absent |
| *consequently* | absent — utiliser *"as a result"* |
| *thus* / *hence* | absent — utiliser *"therefore"* (rare) |
| *indeed* | absent |
| *undoubtedly* / *evidently* | absent |
| *significantly* (comme connecteur d'emphase) | absent comme connecteur ; utilisé comme adverbe de magnitude (*"significantly deteriorated"*) |

**Particularité notable :** le corpus utilise massivement des **participes présents causaux** comme connecteurs implicites (*"leaving European producers at..."*, *"reflecting ongoing challenges..."*, *"keeping European producers..."*). C'est une signature distinctive : la cause est exprimée par un gérondif, pas par un connecteur explicite. Les LLM sous-utilisent cette construction.

**Implication :** Fournir la liste blanche et la liste noire dans le system prompt. Imposer l'utilisation de participes présents causaux comme alternative aux connecteurs explicites.

---

## 18. Gestion des données partielles, préliminaires ou décalées

### Ce que le corpus fait

Le corpus traite systématiquement des **périodes YTD incomplètes** et le fait avec des conventions strictes :

**1. Fenêtre temporelle toujours explicite en clair :**
- *"in the first eight months of 2025"* (CT Q3)
- *"in the first eleven months of 2025"* (CT Q4)
- *"in the first ten months of 2025"* (CT Q4)
- Jamais "in 2025" seul quand les données ne couvrent pas l'année entière

**2. L'astérisque pour les données préliminaires :**
- *"EU27 chemical output (2008-2025*)"* — dans les titres de graphique
- *"Source: Cefic analysis based on Eurostat data, *Jan-Sep 2025"* — dans les lignes de source
- L'astérisque signale que la dernière période est estimée ou incomplète

**3. La formule "compared to the same period in [year]" :**
- Toujours présente quand la comparaison porte sur une période YTD
- Jamais de comparaison YTD vs année complète — c'est une règle non négociable

**4. Le décalage entre indicateurs dans le même rapport :**
- Le CT Q3 mélange des données Jan-Aug (trade) et Jan-Sep (production) dans le même rapport
- Chaque section précise sa propre fenêtre — pas de tentative d'harmoniser artificiellement

### Ce que le corpus ne couvre pas (règles à inventer pour Iris)

Le corpus ne traite jamais explicitement de :
- **Données manquantes** : aucun indicateur n'est absent des rapports analysés
- **Révisions** : le disclaimer F&F mentionne que les données sont révisées rétroactivement, mais le corps du texte n'en fait jamais état

**Règles proposées pour Iris (mensuel, avec latence Eurostat variable) :**

1. **Indicateur indisponible :** Ne pas le mentionner du tout. Pas de "data not yet available" ou de placeholder. Si l'indicateur n'est pas disponible, la section n'existe pas pour cette édition. C'est cohérent avec le pattern Cefic : le Q3 2025 couvre des fenêtres différentes par indicateur sans jamais s'en excuser.

2. **Indicateur avec latence (ex: données à M-2) :** Utiliser la formule standard *"in the first [N] months of [year]"* avec la fenêtre réelle. La transparence du décalage est intégrée dans la formulation, pas dans une note d'excuse.

3. **Révision depuis l'édition précédente :** Si un chiffre a été significativement révisé, le signaler une seule fois par un astérisque + note de bas de section : *"*Revised from [ancien chiffre] published in the [mois] edition, following Eurostat data revision."* Aligné sur le disclaimer F&F mais adapté au format mensuel.

**Implication :** Ces trois règles doivent figurer dans le system prompt comme des non-négociables. La latence est le principal risque de "tell" pour un rapport automatisé — mal gérée, elle signale l'automatisation.
