# EVAL — Fiche 3: Turnover (Sales)

## 3.1 Checklist mécanique (system.md §11)

| # | Check | Verdict |
|---|---|---|
| 1 | Every analytical claim has a number | ✅ |
| 2 | Every number has a benchmark | ✅ (YoY + sector comparison) |
| 3 | Zero banned words | ✅ |
| 4 | No sentence exceeds 35 words | ✅ |
| 5 | Heading is declarative finding with figure | ✅ "EU27 chemical sales fell 7.5% in January 2026" |
| 6 | Source line present, verbatim | ⚠️ Same issue as fiche 2 — uses `(sts_intv_m, 2026)` instead of Cefic format |
| 7 | No concluding paragraph | ✅ |
| 8 | All figures from data block | ✅ |
| 9 | Dates precise | ✅ "January 2026", "January 2025" |
| 10 | British English | ✅ |

## 3.2 Checklist de voix (SYNTHESIS.md)

| Pattern | Observation | Verdict |
|---|---|---|
| P1 (chiffre d'abord) | All sentences data-anchored | ✅ |
| P2 (dual-period) | YoY present, sector benchmark present | ✅ |
| P4 (heading as finding) | "EU27 chemical sales fell 7.5% in January 2026" — strong, correct verb calibration ("fell" for 7.5% = 5-15% range) | ✅ |
| P5 (verbes calibrés) | "fell 7.5%" ✅ (5-15%), "declined by 1.8%" ✅ (1-5%), "down 8.0%" ✅, "steepest decline at 14.2%" ⚠️ — 14.2% is at the top of 5-15% range, "steepest" is acceptable but not from the gradient | ⚠️ |
| P14 (no conclusion) | ✅ Ends on source line |  ✅ |
| P15 (densité chiffrée) | 21 numbers / 5 sentences = 4.2 | ✅ |
| P16 (longueur phrase) | Moyenne: ~24 mots. Longest sentence: 33 words (country rundown). 0/5 ≤15 mots (0%) | ❌ Zero short sentences — entire section is dense compound sentences |
| P17 (connecteurs) | No connectors used at all — pure juxtaposition | ⚠️ Acceptable but monotone |

## 3.3 Tests spécifiques aux patches

| Patch | Test | Verdict |
|---|---|---|
| P2 (fragmented Europe) | All countries negative (FR -3.1% to NL -14.2%). Spread = 11.1 pp > 5 pp → condition met. BUT closing phrase is ABSENT. | ❌ Missing — the model didn't use the closing despite heterogeneity |
| P3 (breakdown optionnel) | Country data present → used ✅. No sub-sector in data → omitted ✅. | ✅ |
| P5 (format unités) | % used consistently. | ✅ |

## 3.4 Diagnostic et patches proposés

**Problème 1 — Zero short sentences.** Every sentence is 20-33 words. The corpus target is 30-40% under 15 words. This makes the section feel dense and LLM-like. The corpus uses short sentences as analytical punctuation ("Chemicals are therefore highly impacted by gas prices." — 8 words).

→ **Patch F:** Add to §2.1 an explicit example: "Include at least one short sentence (under 15 words) per section. Examples from the corpus: 'The decline was widespread.' 'EU27 chemical sales continue to decline.' These provide reading rhythm."

**Problème 2 — "most resilient performance" pattern again.** "France showed the most resilient performance at 101.3, declining by 3.1%." Same qualitative judgement issue as fiche 2.

→ Already covered by proposed Patch D.

**Problème 3 — "fragmented Europe" closing absent.** The heterogeneity condition is clearly met (spread 11.1 pp) but the model did not apply Template 5.3. Likely because all countries are negative — the model may have interpreted the condition literally ("at least one positive AND one negative") and stopped at the first clause, ignoring the OR.

→ **Patch G:** Rephrase §5.3 condition to make the OR more salient: "Apply when EITHER (a) at least one country shows a positive change while another shows a negative change, OR (b) the spread between the highest and lowest country YoY change exceeds 5 pp — even if all countries move in the same direction."
