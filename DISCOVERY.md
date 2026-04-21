# DISCOVERY.md — Projet Iris

**Date :** 17 avril 2026  
**Auteur :** Claude (Phase 1 — Discovery)  
**Reviewer :** Jonathan Mead

---

## 1. Objectif du projet

**Iris** est un pipeline d'analyse de données + site web produisant un **rapport mensuel sur l'industrie chimique européenne** (Monthly Chemical Trends Report).

Le projet vise à automatiser la chaîne complète :
1. Extraction des données (Eurostat, Comext, etc.)
2. Transformation et analyse
3. Génération de rapports au format Cefic
4. Publication sur un site web

---

## 2. Documents de référence trouvés en local

### 2.1 `cefic_data_analysis_memory.md`
- Base de connaissance structurée pour l'agent IA
- Couvre 3 projets : Chemical Industry Insight, Competitiveness Analysis, Trade Dependency Analysis
- Contient les URLs des APIs Eurostat, les formules clés (growth rate, dependency ratio, Herfindahl Index)
- Stack actuelle : Python, Power BI, Excel

### 2.2 `cefic_economic_outlook_style_guide.md` (68 Ko — très détaillé)
- Guide de style complet pour les publications économiques Cefic
- Couvre les deux produits phares :
  - **Facts & Figures** (annuel, 6 chapitres web)
  - **Chemical Trends Report** (trimestriel, PDF 15-25 pages)
- Définit : voix éditoriale, arc narratif, vocabulaire, conventions de quantification, templates, checklists
- **Auteur de référence :** Dr Moncef Hadhri, Chief Economist, `mha@cefic.be`
- **Chiffres-ancres :** €635 Mds turnover, 1.2M emplois, 13% marché mondial, 74% capacity utilisation, gap prix gaz 3x US-EU

---

## 3. Travaux existants dans l'écosystème local

| Répertoire / Fichier | Contenu | Pertinence pour Iris |
|---|---|---|
| `BI AI/Chemical Monthly Report.pbix` | Rapport Power BI mensuel chimie | **Haute** — c'est le prédécesseur probable d'Iris |
| `BI AI/Monthly Chemical Trends 2_0.docx` | Version 2.0 du rapport mensuel | **Haute** — template/brief du rapport |
| `BI AI/Comext/` | Scripts Python d'extraction Comext (download, unzip, dat→csv) | **Haute** — pipeline existant réutilisable |
| `BI AI/Comext/Eurostat Comext.pbix` | Dashboard Power BI Comext | **Moyenne** — référence visuelle |
| `BI AI/comext dashboard/` | Vide | — |
| `BI AI/Prodcom/` | Un email uniquement | **Faible** |
| `BI AI/FTA/` | Free Trade Agreements | **Faible** |
| `Data Analysis/` | Clustering énergie, vidéos formation | **Faible** |

---

## 4. Environnement technique

### 4.1 Machine locale
- **OS :** Windows 11 Enterprise
- **Python :** 3.9.13 (via Microsoft Store)
- **Node.js :** 20.17.0, npm 11.8.0
- **Packages Python notables :** anthropic, aiohttp, pandas (à vérifier), altair
- **Pas de droits admin** — impossible d'installer via winget/msi
- **Git :** disponible, repo local initialisé (branche `master`, aucun commit)

### 4.2 GitHub
- **Repo :** `kendrick7410/iris` (public)
- **Branche par défaut :** `main`
- **Contenu actuel :** README.md + .gitignore (scaffold vide)
- **Pas de `gh` CLI** — accès GitHub limité à git push/pull (si remote configuré)
- **Pas de remote configuré** sur le repo local

### 4.3 Contraintes
- Pas de droits admin → installations via `pip install --user` uniquement
- Pas de `gh` CLI → gestion GitHub via `git` natif + API web
- OneDrive sync → attention aux conflits de fichiers

---

## 5. Sources de données identifiées

### 5.1 Eurostat — Industrial Production Index
- **Dataset :** `sts_inpr_m`
- **API :** `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_inpr_m`
- **Params testés :** `geo=EU27_2020`, `nace_r2=C20`, `unit=I15`, `s_adj=SCA`
- **Statut :** API accessible, format JSON-stat/SDMX. Test initial a retourné structure valide mais valeurs vides (possible problème de paramètres). A investiguer.
- **Données :** Production volume mensuel, index base 2015=100, depuis 1953

### 5.2 Eurostat — GDP
- **Dataset :** `nama_10_gdp`
- **URL :** `https://ec.europa.eu/eurostat/databrowser/view/nama_10_gdp/default/table`

### 5.3 Eurostat — Energy Prices
- **Dataset :** `nrg_pc_202`

### 5.4 Eurostat COMEXT (trade)
- **Scripts existants :** `1 Comext download.py`, `2 Comext unzip.py`, `3 Comext dat to csv.py`
- **Pipeline déjà codé** en local — téléchargement bulk, décompression, conversion

### 5.5 Autres sources mentionnées
- UN Comtrade (`comtrade.un.org`)
- OECD (`stats.oecd.org`)
- IEA (`iea.org`)
- World Bank (`data.worldbank.org`)

---

## 6. Indicateurs clés à couvrir (d'après le style guide)

Les 10 indicateurs du Chemical Trends Report :

| # | Indicateur | Source probable |
|---|---|---|
| 1 | Economic climate (GDP, PMI) | Eurostat / EC surveys |
| 2 | Business climate | European Commission surveys |
| 3 | Output (production volume) | Eurostat `sts_inpr_m` |
| 4 | Producer prices | Eurostat |
| 5 | Total sales | Eurostat |
| 6 | Domestic sales | Eurostat |
| 7 | Extra-EU exports | Eurostat COMEXT |
| 8 | Extra-EU imports | Eurostat COMEXT |
| 9 | Consumption | Calculé (domestic sales + imports - exports) |
| 10 | Capacity utilisation | EC Business surveys |

---

## 7. Architecture pressentie

```
iris/
  data/
    raw/           # Données brutes Eurostat/Comext
    interim/       # Nettoyage intermédiaire
    processed/     # Données prêtes pour analyse
  src/
    extract/       # Scripts d'extraction API
    transform/     # Nettoyage, calculs
    analyze/       # Indicateurs, comparaisons
    report/        # Génération du rapport (PDF/web)
  web/             # Site Next.js ou similaire
  docs/            # Documentation
  tests/
```

(A confirmer en Phase 2 après feu vert de Jonathan.)

---

## 8. Questions ouvertes pour Jonathan

1. **Scope initial :** Faut-il couvrir les 10 indicateurs dès le départ, ou commencer avec un sous-ensemble (ex: output + trade + prices) ?
2. **Format de sortie :** PDF comme le Chemical Trends actuel, site web, ou les deux ?
3. **Fréquence :** Mensuel (comme le titre "Monthly Report") ou trimestriel (comme le format actuel du Chemical Trends) ?
4. **Power BI :** Le `Chemical Monthly Report.pbix` existant est-il le point de départ, ou on repart de zéro en Python ?
5. **Données Comext :** Les scripts existants dans `BI AI/Comext/` sont-ils toujours fonctionnels et à jour ?
6. **Accès GitHub :** Faut-il configurer le remote git vers `kendrick7410/iris` pour pousser le code, ou on travaille uniquement en local pour l'instant ?
7. **Authentification API :** Certaines sources (EC Business Surveys, IEA) nécessitent-elles des clés API ?
8. **Monthly Chemical Trends 2_0.docx :** Puis-je le lire pour comprendre le brief de la v2 du rapport ?

---

## 9. Prochaines étapes proposées (Phase 2 — à valider)

- [ ] Configurer le remote git vers GitHub
- [ ] Créer la structure de répertoires
- [ ] Écrire le `CLAUDE.md` du projet (conventions, architecture, décisions)
- [ ] Prototyper l'extraction d'un premier indicateur (Industrial Production Index)
- [ ] Tester le pipeline Comext existant

---

*En attente du feu vert de Jonathan pour passer en Phase 2.*
