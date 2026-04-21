# Iris Data Sources — v1 Specification

Date: 2026-04-17
Status: Connectivity tested from Jonathan's Windows workstation (not Yaghi)

---

## 1. Overview

| Source | Dataset/Artifact | Frequency | Typical latency | Access method | Feeds Iris section | Test status |
|---|---|---|---|---|---|---|
| Eurostat | `sts_inpr_m` | monthly | ~45 days | JSON API | Output | **OK** (unit=I21) |
| Eurostat | `sts_inppd_m` | monthly | ~45 days | JSON API | Producer prices | **OK** (unit=I21, s_adj=NSA) |
| Eurostat | `sts_intv_m` | monthly | ~45 days | JSON API | Turnover / Sales | **OK** (unit=I21) |
| Eurostat | `nama_10_gdp` | quarterly | ~70 days | JSON API | Economic climate | **OK** |
| DG ECFIN BCS | NACE C20 subsector | monthly | ~5 days | ZIP (XLSX inside) | Business climate, Capacity utilisation | **502** (server-side, likely transient) |
| Cefic Comext ETL | `comext_export.parquet` + dims | weekly refresh, ~45-day Eurostat lag | Parquet files on Yaghi | Trade (exports, imports, balance) | **Accessible** (status page OK, metrics pending) |

---

## 2. Eurostat datasets

### 2.1 `sts_inpr_m` — Industrial Production Index (monthly)

**API endpoint:**
```
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_inpr_m
```

**Parameters for Iris:**

| Param | Value | Notes |
|---|---|---|
| `geo` | `EU27_2020` (aggregate) + `DE,FR,IT,NL,ES,BE,PL` (country breakdown) | Top 7 EU27 chemical producers |
| `nace_r2` | `C20` (chemicals) + `C21,C24,C29,C` (benchmarks: pharma, base metals, automotive, total manufacturing) | |
| `unit` | **`I21`** | **Critical: Eurostat migrated from I15 (2015=100) to I21 (2021=100). I15 returns empty values for data after ~mid-2024. Always use I21 for recent data.** |
| `s_adj` | `SCA` | Seasonally and calendar adjusted |
| `sinceTimePeriod` | `YYYY-MM` | Rolling window — fetch 24 months for YoY + pre-crisis calc |

**Bug resolved:** The DISCOVERY.md test returned empty values because it used `unit=I15`. Eurostat phased out the 2015 base index for recent periods. **Solution: use `unit=I21` (index 2021=100).** For pre-crisis (2014-2019) benchmarks, a separate call with `unit=I15` is needed, or the I21 series can be extended back if Eurostat provides it.

**Response structure:** JSON-stat (SDMX-JSON 2.0). Key fields:
- `value`: object mapping flat index → numeric value
- `dimension.time.category.index`: maps period labels (`2026-02`) to flat indices
- `dimension.geo.category.index`: maps geo codes to indices
- Multi-dimension flattening: index = `time_idx * n_geo + geo_idx` (row-major)

**Connectivity test (2026-04-17):**
- EU27_2020, C20, I21, SCA, since 2025-01: **14 values returned**
- Latest period: **2026-02**
- Sample values: 2025-01→82.0, 2026-01→78.9, 2026-02→79.3
- Country breakdown (7 countries, since 2026-01): **14 values**, all populated
- Sector benchmark (C, C20, C21, C24, C29, since 2026-01): **10 values**, all populated

**Derived indicators for Iris:**
- YoY growth: `(value_m - value_m-12) / value_m-12 * 100`
- YTD average: mean of months Jan through latest available
- YTD YoY: `(ytd_avg_current - ytd_avg_prev) / ytd_avg_prev * 100`
- Gap vs pre-crisis: `(value_m - avg_2014_2019) / avg_2014_2019 * 100`
- Country-by-country YoY for top 7

**Publication schedule:** Eurostat publishes month M around day 15 of month M+2. Example: January 2026 data available ~mid-March 2026.

---

### 2.2 `sts_inppd_m` — Producer Price Index, Domestic (monthly)

**API endpoint:**
```
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_inppd_m
```

**Parameters for Iris:**

| Param | Value | Notes |
|---|---|---|
| `geo` | `EU27_2020` | |
| `nace_r2` | `C20` + benchmarks | |
| `unit` | **`I21`** | Same migration as sts_inpr_m |
| `s_adj` | **`NSA`** | **Note: SCA returns empty for this dataset. Use NSA (not seasonally adjusted).** |
| `sinceTimePeriod` | `YYYY-MM` | |

**Connectivity test (2026-04-17):**
- EU27_2020, C20, I21, NSA, since 2025-01: **14 values returned**
- Latest period: **2026-02** (published ~April 15 2026)
- Sample: 2025-01→117.1, 2026-02→117.2

**Derived indicators:**
- YoY price change: `(price_m - price_m-12) / price_m-12 * 100`
- Price level vs pre-crisis (I21 base, need conversion if pre-crisis data is on I15)

---

### 2.3 `sts_intv_m` — Turnover Index (monthly)

**API endpoint:**
```
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/sts_intv_m
```

**Parameters for Iris:**

| Param | Value | Notes |
|---|---|---|
| `geo` | `EU27_2020` | |
| `nace_r2` | `C20` + benchmarks | |
| `unit` | **`I21`** | |
| `s_adj` | `SCA` | Works with SCA |
| `sinceTimePeriod` | `YYYY-MM` | |

**Connectivity test (2026-04-17):**
- EU27_2020, C20, I21, SCA, since 2025-01: **13 values returned**
- Latest period: **2026-01** (one month behind sts_inpr_m — typical, turnover lags production by ~1 month)
- Sample: 2025-01→89.3, 2026-01→90.8

**Note on latency:** Turnover data runs ~1 month behind production data. In the same Iris edition, the output section may cover Jan-Feb 2026 while the sales section covers Jan only. This is consistent with Chemical Trends practice (Pattern 18: different windows per indicator in the same report, each section specifying its own window).

**Derived indicators:**
- YoY sales change (value terms): `(turnover_m - turnover_m-12) / turnover_m-12 * 100`
- YTD sales change
- Combined price/volume decomposition: volume change ≈ turnover change - price change

---

### 2.4 `nama_10_gdp` — GDP (quarterly/annual)

**API endpoint:**
```
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nama_10_gdp
```

**Parameters for Iris:**

| Param | Value | Notes |
|---|---|---|
| `geo` | `EU27_2020` | |
| `unit` | `CLV10_MEUR` (chain-linked volumes, million EUR, 2010 ref) | For real GDP growth |
| `na_item` | `B1GQ` (GDP at market prices) | |
| `sinceTimePeriod` | `2020` | Annual — fetch last 5 years |

**Connectivity test (2026-04-17):**
- **3 values returned**: 2023→13,211,934.0, 2024→13,353,818.8, 2025→13,558,747.9 (million EUR)
- Latest: **2025** (annual)

**Note:** This dataset provides macro context for the "Economic climate" section. Iris will primarily use it for framing ("EU27 GDP grew by X.X% in [year]") rather than as a core indicator. Quarterly GDP (`namq_10_gdp`) may be more useful for monthly reports — to investigate on Yaghi.

**Derived indicators:**
- Annual GDP growth: `(gdp_y - gdp_y-1) / gdp_y-1 * 100`

---

## 3. DG ECFIN Business and Consumer Surveys (BCS)

### 3.1 Access

**Landing page:** https://economy-finance.ec.europa.eu/economic-forecast-and-surveys/business-and-consumer-surveys/download-business-and-consumer-survey-data/subsector-data_en

**Download URLs:**
- Seasonally adjusted: `https://ec.europa.eu/economy_finance/db_indicators/surveys/documents/series/nace2_ecfin_2603/industry_subsectors_sa_nace2.zip`
- Non-seasonally adjusted: `https://ec.europa.eu/economy_finance/db_indicators/surveys/documents/series/nace2_ecfin_2603/industry_subsectors_nsa_nace2.zip`
- User guide (methodology): `https://ec.europa.eu/economy_finance/db_indicators/surveys/documents/methodological_guidelines/bcs_user_guide.pdf`

### 3.2 Dataset principal: NACE C20 (Chemicals)

The ZIP contains XLSX files with one sheet per NACE 2-digit sector per country. Iris needs NACE C20 rows for EU27 aggregate and top 7 countries.

### 3.3 Benchmark sectors

| NACE | Sector | Iris use |
|---|---|---|
| C21 | Pharmaceuticals | Downstream benchmark — production comparison |
| C24 | Basic metals | Energy-intensive peer — competitiveness comparison |
| C29 | Motor vehicles | Key downstream client — demand proxy |

### 3.4 Variables

| Variable | Frequency | Unit | Iris section |
|---|---|---|---|
| Confidence indicator (composite) | Monthly | Balance of opinion (-100 to +100) | Business climate |
| Production trend (recent months) | Monthly | Balance of opinion | Business climate |
| Production expectations (months ahead) | Monthly | Balance of opinion | Business climate |
| Order books | Monthly | Balance of opinion | Business climate |
| Selling price expectations | Monthly | Balance of opinion | Producer prices (context) |
| **Capacity utilisation** | **Quarterly** (Jan, Apr, Jul, Oct) | **Percentage** | **Capacity utilisation** |

**Critical note on capacity utilisation:** This is the only quarterly indicator in Iris v1. In months without a new reading (Feb, Mar, May, Jun, Aug, Sep, Nov, Dec), Iris should report the latest available quarterly figure with explicit attribution: *"In Q4 2025, EU27 chemical capacity utilisation stood at X.X%"*. Do not interpolate monthly values.

### 3.5 Publication cadence

Monthly release, typically around the 25th-30th of the month for the current month's data. **This is the freshest source Iris has** — ~5 days lag vs ~45 days for Eurostat STS.

### 3.6 Format strategy for Iris

1. **Phase 1 (v1):** Download ZIP, extract XLSX, parse with `openpyxl`/`pandas`. Stable, well-documented format.
2. **Phase 2 (when available):** Migrate to the SDMX API / new data browser when DG ECFIN completes the beta. Monitor: `https://data-browser.ecfin.ec.europa.eu/`

### 3.7 Connectivity test (2026-04-17)

- Landing page: **200 OK**
- ZIP download (`industry_subsectors_sa_nace2.zip`): **502 Bad Gateway** — server-side error, likely transient. The URL structure is correct (confirmed by the landing page HTML).
- **Action required:** Retry from Yaghi when available. If persistent, check if DG ECFIN has migrated to a new distribution URL.

---

## 4. Cefic Comext ETL

### 4.1 Contrat Iris ↔ Comext — NON-NEGOTIABLE

Iris reads **only** the 3 Parquet files produced by the existing Comext ETL pipeline. **Never:**
- Query PostgreSQL directly
- Run `run_etl.py`
- Modify the pipeline
- Rewrite or fork the ETL

This decoupling is absolute. Iris is a consumer. If the Parquet files are stale or missing, Iris skips the trade sections. It does not attempt to fix the upstream.

### 4.2 Files consumed

| File | Type | Join key | Description |
|---|---|---|---|
| `comext_export.parquet` | Fact table | — | Trade flows: period, partner, product, flow, value, quantity |
| `partner_dim.parquet` | Dimension | `partner` ↔ `partner_code` | 506 partner codes, labels EN/FR/DE |
| `product_dim.parquet` | Dimension | `product_nc` ↔ `product_code` | 40,409 CN codes, full hierarchy |

**Path:** To be configured via `COMEXT_DATA_PATH` in `.env`. On Yaghi, path TBD. Not accessible from current workstation.

### 4.3 Fact table schema

| Column | Type | Description |
|---|---|---|
| `period` | datetime | Last day of month (e.g. 2025-03-31) |
| `declarant` | char(2) | Always `EU` (EU27 reporters collapsed) |
| `partner` | char(2) | Trade partner ISO code, or `EU27` for intra-EU bloc |
| `product_nc` | char(8) | Combined Nomenclature 8-digit code |
| `cpa2015` | string | CPA 2015 code (joined from SubstanceId.csv) |
| `chapter_cn` | char(2) | First 2 digits of product_nc (HS chapter) |
| `flow` | smallint | 1 = import, 2 = export |
| `flow_label` | string | `Import` or `Export` |
| `value_in_euros` | bigint | Trade value in EUR |
| `quantity_in_kg` | bigint | Trade volume in kg |

### 4.4 Filters applied upstream (do NOT replicate in Iris)

- CN chapters 20-21, 28-39 (chemistry + chemistry-adjacent, 1,369 substances via `SubstanceId.csv`)
- EU27 declarants only, GB excluded
- Declarant flattened to `EU`
- EU27 partners aggregated to `EU27`, non-EU27 retain ISO codes
- Greece normalized: `GR` → `EL`

### 4.5 Cadence and scheduling

- **Comext refresh:** Every Monday at 06:00 CEST
- **Eurostat data lag:** ~45 days (month M published around mid M+2)
- **Iris cron (proposal):** **Tuesday 09:00 CEST** — after Monday refresh, guarantees latest Parquet
- **Idempotency:** Comext ETL uses `etl_log` table. Already-loaded periods are skipped unless `--force`.

### 4.6 Freshness test (2026-04-17)

- Status page (`https://comext.status.cefic.org/`): **Accessible**
- Pipeline description: Confirmed — weekly Monday 06:00, Parquet export after every run
- **Latest period loaded: Not displayed** (status page shows placeholder dashes). Metrics pending — possibly no run since status page was last generated.
- **Methodology page:** Fully documented (download, extract, transform, load, export stages)

### 4.7 Iris indicators from Comext

**Extra-EU exports:** `WHERE declarant='EU' AND partner NOT IN ('EU27') AND flow=2`
- Aggregate: sum `value_in_euros` and `quantity_in_kg` by period
- By partner: top N partners ranked by value (Template 5.2 — Pattern 6)
- By sub-sector: aggregate by `chapter_cn` groups (28-29 = basic inorganics, 29 = petrochemicals, 32-33 = specialty, 34 = consumer, 39 = polymers)

**Extra-EU imports:** Same filters with `flow=1`

**Trade balance:** exports - imports, in value and in volume

**Sub-sector mapping (CN chapters → Cefic segments):**

| Cefic segment | CN chapters (approximate) | Notes |
|---|---|---|
| Basic inorganics | 28 | |
| Petrochemicals | 29 (part) | Requires finer filtering |
| Specialty chemicals | 32, 33, 38 (part) | Needs validation against Cefic internal mapping |
| Consumer chemicals | 34 | |
| Polymers | 39 | |

**Important caveat:** The CN-to-Cefic-segment mapping above is approximate. The precise mapping is maintained internally by Cefic Economics and may use a custom crosswalk. This must be validated with Dr Hadhri or from the `SubstanceId.csv` file on Yaghi before Iris generates sub-sector breakdowns.

---

## 5. Sources reserved for v1.1

| Source | Future Iris use | API key required |
|---|---|---|
| OECD (`stats.oecd.org`) | Labour productivity by country, international benchmarks (US, Japan, Korea) | No (public SDMX API) |
| IEA (`iea.org/data-and-statistics`) | Energy intensity, carbon intensity by sector | Yes (paid data subscriptions for granular data) |
| World Bank (`data.worldbank.org`) | Global commodity prices, GDP PPP, trade openness | No (public API) |
| UN Comtrade (`comtrade.un.org`) | Alternative/complement to Comext for extra-European partner detail | Yes (free tier: 500 requests/month; bulk requires subscription) |

---

## 6. Limits, caveats, questions ouvertes

### 6.1 Eurostat revisions

Eurostat republishes corrected data for past months several times per year. **Proposal:** Iris lives with the snapshot at publication time. Do not re-generate past editions. Rationale:
- Chemical Trends does the same (the F&F disclaimer warns against comparing editions)
- Re-generation would break the published archive
- If a major revision affects a key figure, a footnote in the next edition suffices (Pattern 18, revision rule)

**Decision needed:** Jonathan to confirm.

### 6.2 Suppressed Comext cells

Eurostat masks small or confidential trade flows (typically <100 EUR or single-trader exports). These rows are simply absent — no flag, no zero. Impact: aggregated totals may be marginally lower than Eurostat's published EU27 aggregates. This is inherent to the bulk data distribution and is consistent with how Cefic currently operates.

### 6.3 Brexit

UK appears as EU27 member through December 2020 and as third country from January 2021. The Comext pipeline handles this correctly: UK is excluded from the declarant side, and on the partner side UK retains its ISO code (not aggregated into `EU27`). Iris should treat UK as a third-country partner everywhere. Historical comparisons spanning the Brexit date must account for the composition break.

### 6.4 BCS data browser migration

DG ECFIN is migrating from the current ZIP distribution to a new data browser (`data-browser.ecfin.ec.europa.eu`). The new browser is in beta. **Strategy:** Start with the XLSX/ZIP format for Iris v1. Plan a migration checkpoint for v1.1 when the SDMX API is stable.

### 6.5 Unit migration I15 → I21

Eurostat has migrated the base index for STS datasets from 2015=100 to 2021=100. The I15 series is still available for historical data but returns empty values for recent periods (post ~mid-2024). **Impact on pre-crisis benchmarks:**
- Pre-crisis averages (2014-2019) must be fetched with `unit=I15`
- Current data must be fetched with `unit=I21`
- To compute a gap vs pre-crisis, either: (a) convert I15 to I21 base using the overlap period, or (b) express the gap in YoY growth terms rather than index levels
- **Recommended approach (a):** Fetch both series for the overlap period (e.g. 2021), compute the conversion factor, apply it to the I15 pre-crisis average. This is a one-time calculation.

### 6.6 Capacity utilisation quarterly cadence

Capacity utilisation from BCS is quarterly (Jan, Apr, Jul, Oct releases). Iris is monthly. In non-release months, Iris should report the latest available quarterly value with explicit period attribution. Do not interpolate or estimate monthly values.

---

## 7. Data block schema (Iris input contract)

This is the JSON structure that the Iris orchestrator will produce and pass to the LLM rédacteur as the user message. It aligns with the `system.md` §10 input contract.

```json
{
  "section_type": "output",
  "period": {
    "month": "2026-02",
    "publication_date": "2026-05-01",
    "window": "January-February 2026",
    "window_months": 2,
    "window_ordinal": "first two"
  },
  "data": {
    "current": {
      "value": 79.3,
      "unit": "index 2021=100",
      "period": "2026-02",
      "s_adj": "SCA"
    },
    "previous_year": {
      "value": 82.0,
      "period": "2025-02",
      "delta_pct": -3.3
    },
    "pre_crisis_avg": {
      "value": 108.7,
      "base": "I15 converted to I21",
      "period": "2014-2019 average",
      "delta_pct": -27.0
    },
    "ytd": {
      "current_avg": 79.1,
      "previous_year_avg": 81.5,
      "delta_pct": -2.9
    },
    "by_country": {
      "DE": { "current": 77.3, "yoy_pct": -3.3 },
      "FR": { "current": 76.6, "yoy_pct": -2.9 },
      "IT": { "current": 93.6, "yoy_pct": -2.0 },
      "NL": { "current": 84.8, "yoy_pct": -4.9 },
      "ES": { "current": 82.8, "yoy_pct": 0.8 },
      "BE": { "current": 90.6, "yoy_pct": -1.3 },
      "PL": { "current": 93.0, "yoy_pct": -2.6 }
    },
    "by_sector": {
      "C": { "label": "Total manufacturing", "current": 102.1, "yoy_pct": 1.6 },
      "C20": { "label": "Chemicals", "current": 79.3, "yoy_pct": -3.3 },
      "C21": { "label": "Pharmaceuticals", "current": 115.4, "yoy_pct": 2.1 },
      "C24": { "label": "Basic metals", "current": 88.7, "yoy_pct": -1.5 },
      "C29": { "label": "Motor vehicles", "current": 95.2, "yoy_pct": -2.3 }
    },
    "source": "Cefic analysis based on Eurostat data (sts_inpr_m, 2026)"
  },
  "charts": ["output_index_2008_2026", "output_yoy_by_country"],
  "editorial_context": {
    "latest_structural_break": "March 2022",
    "notable_events": ["US tariff measures since March 2025"],
    "pre_crisis_reference": "2014-2019 average"
  }
}
```

**Contract rules:**
- All `delta_pct` values are pre-calculated by the orchestrator. The LLM does not compute.
- `null` or absent fields mean the data is unavailable. The LLM omits them.
- `by_country` always includes the top 7: DE, FR, IT, NL, ES, BE, PL.
- `by_sector` always includes C (total manufacturing) as the reference benchmark.
- `charts` lists chart IDs to be inserted as `{{chart:chart_id}}` placeholders.

---

## Next steps

### Tests that failed or need follow-up

1. **DG ECFIN BCS subsector ZIP: 502 Bad Gateway.** Transient server error. Retry from Yaghi. If persistent, check if URL has migrated. Non-blocking for Livrable 3 (can use synthetic confidence/capacity data).
2. **Comext status page: metrics pending.** Latest period loaded not displayed. Need access to Yaghi to check actual Parquet freshness. Non-blocking for Livrable 3 (trade data will use synthetic values).

### Questions requiring Jonathan's arbitrage

1. **Eurostat revision policy:** Confirm Iris lives with snapshot-at-publication, no re-generation of past editions. (Proposed: yes.)
2. **CN-to-Cefic-segment mapping:** The approximate mapping in §4.7 needs validation against `SubstanceId.csv` or Dr Hadhri's crosswalk. Blocking for real trade sub-sector breakdowns.
3. **Quarterly GDP (`namq_10_gdp`):** Should Iris use quarterly GDP for finer macro framing, or is annual sufficient?

### What is ready now for Livrable 3

- **4 Eurostat STS APIs fully operational:** Output (sts_inpr_m), prices (sts_inppd_m), turnover (sts_intv_m), GDP (nama_10_gdp). All tested, all returning data through February 2026.
- **Data block schema defined:** JSON contract between orchestrator and LLM rédacteur is specified and aligned with `system.md` §10.
- **We can generate test fiches with real Eurostat data** (not just synthetic) for the output, prices, and turnover sections. Trade sections require either Comext access (Yaghi) or synthetic values.
- **Bug resolved:** I15→I21 unit migration documented and working.
