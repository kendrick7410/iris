# SUMMARY — Stress-test du system.md v1 (3 fiches, données réelles)

## 1. Patterns qui tiennent

| Pattern | Résultat | Commentaire |
|---|---|---|
| P1 (chiffre d'abord) | ✅ 3/3 | Le system prompt impose efficacement la densité chiffrée |
| P2 (dual-period) | ✅ 3/3 | Toutes les sorties incluent au moins un benchmark YoY + un benchmark sectoriel |
| P4 (heading as finding) | ✅ 3/3 | Headings déclaratifs avec chiffres à chaque fois |
| P10 (3e personne) | ✅ 3/3 | Zéro "we", zéro "our" |
| P14 (no conclusion) | ✅ 3/3 | Aucun paragraphe de conclusion |
| P17 (connecteurs bannis) | ✅ 3/3 | Zéro connecteur banni détecté |
| P15 (densité chiffrée) | ✅ 3/3 | Ratios de 3.2 à 4.2 chiffres/phrase — excellent |

**Verdict : le cœur du registre tient.** Les règles MUST sont respectées partout.

## 2. Patterns qui dérivent

| Problème | Fréquence | Gravité | Type |
|---|---|---|---|
| **Source line copie le JSON au lieu du format Cefic** | 2/3 (fiches 2, 3) | Moyenne | Template mal appliqué |
| **Zéro phrases courtes (≤15 mots)** | 2/3 (fiches 2, 3) | Moyenne | Rythme trop dense |
| **"Most resilient performance" — jugement qualitatif** | 2/3 (fiches 2, 3) | Faible | Vocabulaire hors registre |
| **Ranking par valeur d'index au lieu du mouvement YoY** | 1/3 (fiche 2) | Faible | Template mal adapté aux prix |
| **"Fragmented Europe" absent malgré hétérogénéité** | 1/3 (fiche 3) | Faible | Condition OR mal interprétée |
| **Charts empilés sans prose intermédiaire** | 1/3 (fiche 1) | Faible | Structure incomplète |

## 3. Patches consolidés (top 5, par priorité)

### Patch 1 — Source line : ne pas copier le JSON (HIGH)
**Section §9, ajouter règle 7 :**
"The source line must follow Template 5.4 format exactly. Do not copy the `source` field from the data block — it is metadata. Write: `Source: Cefic analysis based on Eurostat data (2026)` or `Source: Cefic analysis based on Eurostat data (2026, NACE code 20)`."

### Patch 2 — Au moins une phrase courte par section (MEDIUM)
**Section §2.1, ajouter :**
"Include at least one short sentence (under 15 words) per section as analytical punctuation. Examples: 'The decline was widespread across major producers.' 'EU27 chemical sales continue to decline.' These provide reading rhythm and prevent the dense-compound-sentence monotony typical of LLM output."

### Patch 3 — Interdire les jugements qualitatifs (MEDIUM)
**Section §8, ajouter anti-pattern 8.6 :**
"❌ 'Italy showed the most resilient performance at 0.3%.'
✅ 'Italy reported the smallest decline at 0.3%.'
Avoid qualitative judgements (resilient, robust, fragile, encouraging, disappointing). State the magnitude and let the reader judge."

### Patch 4 — Ranking par mouvement, pas par niveau d'index (LOW)
**Section §5.2, ajouter note :**
"For price indices and production indices, rank countries/sectors by YoY change (the finding), not by absolute index level (which reflects base effects). Example: 'The Netherlands experienced the steepest price decline at 9.2%, followed by Belgium (5.5%) and France (3.0%).'"

### Patch 5 — Fragmented Europe : clarifier la condition OR (LOW)
**Section §5.3, reformuler :**
"Apply when EITHER (a) at least one country shows a positive YoY change while another shows a negative one, OR (b) the spread between the highest and lowest country YoY exceeds 5 pp — even if all countries move in the same direction."

## 4. Questions éditoriales pour Jonathan

1. **Faut-il que chaque chart soit précédé d'un commentaire analytique ?** Le corpus Cefic intercale toujours une phrase entre chaque graphique. Si oui, j'ajoute une règle dans §6.1.

2. **Le heading doit-il contenir le benchmark pre-crisis ou le YoY ?** Fiche 1 utilise le pre-crisis ("18% below pre-crisis"), fiches 2 et 3 utilisent le YoY ("down 2.8%", "fell 7.5%"). Les deux sont valides dans le corpus. Faut-il une règle de préférence ?

3. **La formule "The decline was widespread" est-elle trop vague ?** Elle n'est pas ancrée sur un chiffre (violation de P1), mais elle sert de transition analytique. Le corpus ne l'utilise pas — mais le corpus ne manque jamais de phrases courtes factuelles. Faut-il l'autoriser comme exception de rythme ?
