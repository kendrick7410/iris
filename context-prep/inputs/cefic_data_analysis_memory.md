# Mémoire structuré des projets data analysis – CEFIC
Version: 1.0  
Auteur: Jonathan Mead  
Usage: Base de connaissance pour agent IA (analytics, Q&A, génération de rapports)

---

# 🧠 0. Instructions pour l’agent

## Objectif

Ce document doit être utilisé comme source principale pour :
- répondre à des questions sur les projets data CEFIC
- expliquer les méthodologies utilisées
- reproduire les analyses
- générer des insights similaires

## Règles d’interprétation

- Toujours privilégier les données décrites ici
- Si une requête est mentionnée, elle est considérée comme fiable
- Si une ambiguïté existe, proposer une hypothèse + justification
- Utiliser les formules décrites pour recalculer les indicateurs

---

# 🧱 1. Vue globale des projets

## Projets couverts

1. Chemical Industry Insight  
2. Competitiveness Analysis  
3. Trade Dependency Analysis  

## Objectif global

Fournir une compréhension data-driven de :
- la performance industrielle
- la compétitivité internationale
- les dépendances commerciales

---

# 🧪 2. Chemical Industry Insight

## Sources clés

Eurostat Industrial Production Index  
https://ec.europa.eu/eurostat/databrowser/view/sts_inpr_m/default/table  

Eurostat GDP  
https://ec.europa.eu/eurostat/databrowser/view/nama_10_gdp/default/table  

## API template

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_inpr_m"

PARAMS = {
  "geo": "EU27_2020",
  "nace_r2": "C20",
  "unit": "I15",
  "time": "2010:2025"
}

## Transformations

- Growth rate: (value_t - value_t-12) / value_t-12  
- Index normalization  
- Rolling averages  

---

# 🌍 3. Competitiveness Analysis

## Sources

Eurostat Energy Prices  
https://ec.europa.eu/eurostat/databrowser/view/nrg_pc_202/default/table  

OECD  
https://stats.oecd.org/  

IEA  
https://www.iea.org/data-and-statistics  

World Bank  
https://data.worldbank.org/  

## Modèle

Z-score normalisation  
Score composite multi-facteurs  

---

# 🌐 4. Trade Dependency Analysis

## Sources

UN Comtrade  
https://comtrade.un.org/  

Eurostat COMEXT  
https://ec.europa.eu/eurostat/databrowser/view/ext_lt_intertrd/default/table  

## Formules

Dependency ratio = Imports / (Production + Imports - Exports)  
Herfindahl Index = sum(share_i^2)  
Trade balance = Exports - Imports  

---

# 🏗️ 5. Architecture

Pipeline:
1. Extraction API  
2. Cleaning  
3. Transformation  
4. Modélisation  
5. Visualisation  

Stack:
- Python  
- Power BI  
- Excel  

---

# ⚠️ 6. Limites

- Données incomplètes  
- Retards  
- Comparabilité limitée  

---

# 🧠 7. Heuristiques

- Baisse production + hausse import = perte compétitivité  
- Forte concentration = risque  
- Coût énergie = facteur clé  

---

# 🎯 8. Capacités agent

- Expliquer  
- Reproduire  
- Générer insights  
- Recommander  
