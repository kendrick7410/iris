# EVAL — Fiche 2: Producer Prices

## 3.1 Checklist mécanique (system.md §11)

| # | Check | Verdict |
|---|---|---|
| 1 | Every analytical claim has a number | ✅ |
| 2 | Every number has a benchmark | ✅ (YoY + sector comparison) |
| 3 | Zero banned words | ✅ |
| 4 | No sentence exceeds 35 words | ✅ (longest: ~30 words) |
| 5 | Heading is declarative finding with figure | ✅ "EU27 chemical prices down 2.8% in February 2026" |
| 6 | Source line present, verbatim | ⚠️ Uses `(sts_inppd_m, 2026)` — the dataset code is internal metadata, not the Cefic format. Should be `(2026)` or `(2026, NACE code 20)`. |
| 7 | No concluding paragraph | ✅ |
| 8 | All figures from data block | ✅ |
| 9 | Dates precise | ✅ |
| 10 | British English | ✅ |

## 3.2 Checklist de voix (SYNTHESIS.md)

| Pattern | Observation | Verdict |
|---|---|---|
| P1 (chiffre d'abord) | All sentences carry data | ✅ |
| P2 (dual-period) | YoY present, sector benchmark present, no pre-crisis (null in data → correctly omitted) | ✅ |
| P4 (heading as finding) | "EU27 chemical prices down 2.8% in February 2026" — strong | ✅ |
| P5 (verbes calibrés) | "decreased by 2.8%" ✅ (1-5% unmarked), "edged up by 0.2%" ✅ (<1%), "steepest decline at 5.5%" ⚠️, "sharpest drop at 9.2%" ⚠️ | ⚠️ "steepest" and "sharpest" used for 5.5% and 9.2% — the gradient says 5-15% = "fell/dropped". "Sharpest" is acceptable for 9.2% but "steepest" for 5.5% is borderline. |
| P14 (no conclusion) | ✅ |
| P15 (densité chiffrée) | 16 numbers / 5 sentences = 3.2 | ✅ |
| P16 (longueur phrase) | Moyenne: ~20 mots. 1/5 ≤15 mots (20%) | ⚠️ Below target |
| P17 (connecteurs) | "However" ✅ approved | ✅ |

## 3.3 Tests spécifiques aux patches

| Patch | Test | Verdict |
|---|---|---|
| P2 (fragmented Europe) | "These chemical price trends by country show a fragmented Europe." — IT -0.3% vs NL -9.2% → spread 8.9 pp → justified. BUT: all countries are negative. The condition says "at least one positive AND one negative" OR spread >5pp. Spread passes, so ✅. | ✅ |
| P3 (breakdown optionnel) | Country breakdown present in data → used. No sub-sector data → correctly omitted. | ✅ |
| P5 (format unités) | % used consistently ✅. No €bn needed for prices. | ✅ |

## 3.4 Diagnostic et patches proposés

**Problème 1 — Ranking template appliqué maladroitement aux prix.** "With 126.4, Belgium reported the highest price index level, followed by Poland (118.4) and Germany (119.0)." Le template Pattern 6 est conçu pour des montants €bn, pas des niveaux d'index. Classer les pays par *niveau d'index* n'a pas de sens analytique — c'est le *mouvement* (YoY) qui compte pour les prix.

→ **Patch C:** Ajouter dans §5.2 une note : "For price indices and production indices, the ranking template should rank by YoY change (the analytical finding), not by absolute index level (which reflects base effects and composition). Example: 'The Netherlands experienced the steepest price decline at 9.2%, followed by Belgium (5.5%) and France (3.0%).'"

**Problème 2 — "most resilient performance"** est du vocabulaire interprétatif, pas descriptif-analytique. Le corpus ne qualifie jamais un pays de "résilient" — il donne le chiffre.

→ **Patch D:** Ajouter aux anti-patterns §8 : "❌ 'Italy showed the most resilient performance' ✅ 'Italy reported the smallest decline at 0.3%.' Avoid qualitative judgements (resilient, robust, fragile). State the magnitude."

**Problème 3 — Source line contient le code dataset.** `(sts_inppd_m, 2026)` n'est pas le format Cefic. Devrait être `(2026)` ou `(2026, NACE code 20)`.

→ Déjà couvert par §5.4 mais le modèle a copié le champ `source` du JSON littéralement. **Patch E:** Ajouter dans §9 (output contract) : "The source line must follow Template 5.4 format. Do not copy the `source` field from the data block verbatim — it is metadata for traceability, not the published caption."
