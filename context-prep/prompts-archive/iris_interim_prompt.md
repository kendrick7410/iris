# Prompt intermédiaire — Travail éditorial pendant l'attente de Yaghi

> À coller dans la session Claude Code en cours.
> Ce prompt remplace temporairement la Phase 2. On reprendra le bootstrap structurel quand Yaghi sera dispo.

---

Stop sur le bootstrap. Le DISCOVERY a été fait sur mon PC Windows, mais la production d'Iris tournera sur le serveur Yaghi (Linux), où se trouvent le projet Comext réel et le dossier `docs-cefic`. Tant que je n'ai pas accès à Yaghi, on ne peut pas trancher l'architecture correctement.

Pendant ce temps, on va **travailler le fond éditorial**, qui ne dépend d'aucun environnement. C'est la partie la plus critique d'Iris et on peut avancer dessus maintenant à 100%.

## Ne crée aucune structure de repo, aucun bootstrap, aucun CLAUDE.md

Tout ce qui suit est du travail de préparation qui vivra dans un dossier `~/iris/context-prep/` (nom temporaire). Quand on fera le vrai bootstrap sur Yaghi, on déplacera ces artefacts dans la structure finale.

## Phase intermédiaire — 3 livrables

### Livrable 1 — Corpus de référence Cefic

Construis un corpus annoté de publications Cefic réelles pour ancrer la voix.

1. Fetch sur cefic.org **au moins 6 publications** couvrant la diversité éditoriale :
   - 2 *Chemical Trends Report* récents (différents trimestres)
   - 2 sections de *Facts & Figures* (édition récente)
   - 2 *Economic Bulletin* ou équivalents courts

2. Pour chaque publication, enregistre dans `context-prep/corpus/` :
   - Le texte brut extrait (`.md`)
   - Une **fiche d'annotation** (`.annotated.md`) qui isole :
     - Les 3-5 phrases d'ouverture les plus caractéristiques
     - 3 exemples de commentaire de graphique (la phrase qui suit un chiffre)
     - 3 tournures de comparaison temporelle (YoY, vs previous quarter)
     - 2 formulations de nuance / prudence ("remains subdued", "continues to weigh on", etc.)
     - Le paragraphe de conclusion-type

3. À la fin, un `corpus/SYNTHESIS.md` qui extrait les **patterns transversaux** : 10-15 caractéristiques de la voix Cefic observées empiriquement, avec 2 exemples chacune tirés du corpus. C'est la base de ce qui ira dans le system prompt d'Iris.

### Livrable 2 — Premier `system.md` éditorial, testé

À partir du style guide existant + du corpus annoté, rédige une **première version du system prompt** qui sera injecté à chaque appel de rédaction d'Iris.

Emplacement : `context-prep/editorial/system.md`.

Structure attendue :
- Identité du rédacteur (Cefic Economics team, pas un LLM)
- Voix : registre, longueur de phrase, densité chiffrée
- Règles non-négociables (pas d'invention, sources tracées, dual-period comparison, EU27_2020, HS 28-39)
- Structure-type d'une section (ouverture → chiffre clé → contexte → nuance → implication)
- Exemples positifs et négatifs (prendre directement du corpus pour les positifs, rédiger des contre-exemples génériques-LLM pour les négatifs)
- Checklist finale que le rédacteur doit cocher mentalement avant de rendre

### Livrable 3 — Test en boucle fermée du system prompt

Tant qu'on n'a pas les vraies données Eurostat, on teste le system prompt avec des **chiffres factices mais plausibles**.

1. Dans `context-prep/editorial/test-inputs/`, crée 3 fiches de données factices représentant 3 mois fictifs (par ex. mars, avril, mai 2026). Chaque fiche contient : les 4 indicateurs v1 (production, exports, imports, producer prices), valeurs courantes + N-1, source citée, une note contextuelle.

2. Pour chacune, appelle l'API Anthropic (Sonnet) avec le `system.md` en system et la fiche de données en user, et génère un brouillon de **section "Output"** (un seul indicateur, pas le rapport entier).

3. Sauve les 3 sorties dans `context-prep/editorial/test-outputs/`.

4. Auto-évalue chaque sortie contre le `SYNTHESIS.md` du Livrable 1. Produis un `test-outputs/EVAL.md` qui note pour chaque sortie :
   - ✅ ce qui sonne Cefic
   - ❌ ce qui sonne encore LLM générique
   - Les 3 patches à apporter au `system.md` pour corriger

5. **Itère une fois** : applique les patches, re-génère une des 3 sorties, compare.

## Ce que ça me donne quand Yaghi revient

- Un `system.md` déjà stress-testé, pas un premier jet naïf
- Un corpus annoté qu'on pourra injecter en few-shot si besoin
- Une vraie intuition sur où le LLM dérive, donc où mettre les garde-fous dans les prompts de rédaction
- Zéro dette technique, puisqu'on n'a touché à aucune archi

## Contraintes

- **Aucune création de repo ou de branche Iris structurelle.** Tout dans `~/iris/context-prep/`, dossier temporaire qu'on déplacera ou supprimera.
- **Ne modifie pas `DISCOVERY.md`.** Il reste tel quel, il sera réconcilié avec les vraies observations Yaghi plus tard.
- **Pas de commit ni de push.** On n'est pas encore sur la structure finale.
- Si l'API Anthropic n'est pas accessible (clé manquante, rate limit), fais tout le travail sauf le Livrable 3 et note-le.

Commence par le Livrable 1. Présente-moi `corpus/SYNTHESIS.md` avant de passer au Livrable 2.
