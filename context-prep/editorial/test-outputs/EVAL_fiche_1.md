# EVAL — Fiche 1: Output (Production)

## 3.1 Checklist mécanique (system.md §11)

| # | Check | Verdict |
|---|---|---|
| 1 | Every analytical claim has a number | ✅ |
| 2 | Every number has a benchmark | ✅ (YoY + pre-crisis + sector comparisons) |
| 3 | Zero "we/our/furthermore/moreover/in conclusion/notably/consequently" | ✅ |
| 4 | No sentence exceeds 35 words | ✅ (longest: 33 words in country paragraph) |
| 5 | Heading is declarative finding with figure | ✅ "EU27 chemical output remains 18% below pre-crisis levels" |
| 6 | Source line present, verbatim format | ✅ `Source: Cefic analysis based on Eurostat data (2026)` |
| 7 | No concluding paragraph | ✅ Ends on chart + source |
| 8 | All figures from data block | ✅ All values verified against JSON |
| 9 | Dates precise | ✅ "February 2026", "2014–2019 average" |
| 10 | British English | ⚠️ "2014–2019" renders as "2014�2019" — encoding issue, not editorial |

## 3.2 Checklist de voix (SYNTHESIS.md)

| Pattern | Observation | Verdict |
|---|---|---|
| P1 (chiffre d'abord) | Every sentence leads with or contains a number | ✅ |
| P2 (dual-period) | YoY + pre-crisis + sector benchmarks all present | ✅ |
| P4 (heading as finding) | "EU27 chemical output remains 18% below pre-crisis levels" — declarative, with figure | ✅ |
| P5 (verbes calibrés) | "down by 3.9%" (1-5% = unmarked ✅), "decreased by 8.6%" (5-15% = unmarked, acceptable), "increased by 2.0%" ✅ | ✅ |
| P14 (no conclusion) | Ends on chart/source | ✅ |
| P15 (densité chiffrée) | 26 numbers / 8 sentences = 3.25 chiffres/phrase | ✅ |
| P16 (longueur phrase) | Moyenne: ~22 mots. 2/8 phrases ≤15 mots (25%) | ⚠️ Slightly below target 30-40% of short sentences |
| P17 (connecteurs) | "By contrast" ✅ approved. No banned connectors. | ✅ |

## 3.3 Tests spécifiques aux patches

| Patch | Test | Verdict |
|---|---|---|
| P2 (fragmented Europe) | FR +1.1% vs NL -9.6% → spread 10.7 pp → heterogeneity confirmed → closing justified | ✅ |
| P3 (breakdown optionnel) | Both country and sector breakdowns present in data block → both used | ✅ |
| P5 (format unités) | Index values dimensionless ✅, percentages with % ✅ | ✅ |

## 3.4 Diagnostic et patches proposés

**Problème 1 — Ranking template pas utilisé pour les pays.** Le country breakdown liste les pays par valeur d'index, pas avec le template "With [value], [country] is the [rank]..." du Pattern 6. La structure "Poland reported the highest... Spain followed... France at..." est acceptable mais diverge du template canonique inversé.

→ **Patch A:** Ajouter une note dans §5.2 : le ranking template s'applique aussi aux index values, pas seulement aux €bn. Adapter l'exemple : "With 100.9, Poland reported the highest chemical production index among major EU27 producers."

**Problème 2 — Deux charts sans séparation analytique.** Les deux `{{chart:...}}` sont collés à la fin sans texte intermédiaire. Le corpus Cefic intercale un commentaire entre chaque chart.

→ **Patch B:** Ajouter dans §6.1 : "If multiple charts are provided, each chart must be preceded by at least one analytical sentence. Do not stack charts without intervening prose."

**Problème 3 — Encodage UTF-8.** Le en-dash "–" dans "2014–2019" est rendu comme "�". Problème technique (Python encoding), pas éditorial. À résoudre dans l'orchestrateur, pas dans le system prompt.
