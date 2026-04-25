/**
 * Single source of truth for derived edition data.
 *
 * Both the dashboard (`pages/editions/[id].astro`) and the print layout
 * (`pages/editions/[id]/print-layout.astro`) consume this so the rendered
 * content stays identical between the live site and the generated PDF.
 *
 * Inputs: an Astro content-collection `entry` (the MDX file) plus the
 * sibling JSON fiches and chart SVGs produced by the Iris pipeline.
 *
 * Outputs: a single object with everything the consumers need — parsed
 * MDX sections, KPI cards, sparklines, partner/balance/waterfall chart
 * specs, etc. No JSX — consumers handle rendering.
 */
import fs from 'node:fs';
import path from 'node:path';
import type { CollectionEntry } from 'astro:content';

// ────────────────────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────────────────────

export type SeriesPoint = { period: string; value: number };
export type BalancePoint = { period: string; value_eur_bn: number };

export type MdxSection = {
  title: string;
  paragraphs: string[];
  images: { src: string; alt: string }[];
  source: string | null;
};

export type Kpi = {
  label: string;
  value: string;
  delta: string;
  dir: 'pos' | 'neg';
  foot: string;
};

export type PartnerCard = {
  code: string;
  label: string;
  value_now: string;
  delta_value: string;
  yoy_pct: string;
  dir: 'pos' | 'neg';
  share_pct: string;
  top_chapters: Array<{ label: string; yoy_pct: string; value_now: string }>;
};

// ────────────────────────────────────────────────────────────────────────
// Date / format helpers
// ────────────────────────────────────────────────────────────────────────

export const monthName = (id: string) => {
  const [y, m] = id.split('-');
  const d = new Date(Number(y), Number(m) - 1, 1);
  return d.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
};

export const monthShort = (id: string) => {
  const [y, m] = id.split('-');
  const d = new Date(Number(y), Number(m) - 1, 1);
  return d.toLocaleDateString('en-GB', { month: 'short', year: '2-digit' });
};

export const fmtMonth = (ym: string) => {
  const [y, m] = ym.split('-');
  const d = new Date(Number(y), Number(m) - 1, 1);
  return d.toLocaleDateString('en-GB', { month: 'short', year: '2-digit' });
};

// ────────────────────────────────────────────────────────────────────────
// MDX section parsing
// ────────────────────────────────────────────────────────────────────────

export function parseMdxSections(body: string | undefined): MdxSection[] {
  if (!body) return [];
  return body
    .split(/\n---+\n/)
    .map(parseMdxSection)
    .filter((s): s is MdxSection => s !== null);
}

function parseMdxSection(block: string): MdxSection | null {
  const lines = block.trim().split('\n');
  const titleIdx = lines.findIndex((l) => l.startsWith('## '));
  if (titleIdx < 0) return null;
  const title = lines[titleIdx].replace(/^##\s+/, '').trim();
  const rest = lines.slice(titleIdx + 1);
  const images: { src: string; alt: string }[] = [];
  let source: string | null = null;
  const proseLines: string[] = [];
  for (const line of rest) {
    const m = line.match(/<img\s+src="([^"]+)"\s+alt="([^"]+)"\s*\/?>/);
    if (m) {
      images.push({ src: m[1], alt: m[2] });
    } else if (/^Source:/i.test(line.trim())) {
      source = line.trim();
    } else {
      proseLines.push(line);
    }
  }
  const paragraphs = proseLines
    .join('\n')
    .split(/\n{2,}/)
    .map((p) => p.trim().replace(/\s+/g, ' '))
    .filter(Boolean);
  return { title, paragraphs, images, source };
}

export function inlineMd(text: string): string {
  return text
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
}

// ────────────────────────────────────────────────────────────────────────
// Filesystem helpers (resolved against the Astro CWD = site/)
// ────────────────────────────────────────────────────────────────────────

const PROJECT_ROOT = path.resolve('..');

function readFiche(editionId: string, name: string): any | null {
  try {
    const p = path.join(PROJECT_ROOT, 'data', 'processed', editionId, 'fiches', `${name}.json`);
    return JSON.parse(fs.readFileSync(p, 'utf8'));
  } catch {
    return null;
  }
}

function chartExists(editionId: string, id: string): boolean {
  try {
    return fs.statSync(path.resolve(`public/charts/${editionId}/${id}.svg`)).isFile();
  } catch {
    return false;
  }
}

// ────────────────────────────────────────────────────────────────────────
// Spark chart builder
// ────────────────────────────────────────────────────────────────────────

export type SparkSpec = ReturnType<typeof buildSpark>;

export function buildSpark(
  series: SeriesPoint[] | null | undefined,
  stroke: string,
  unit: string,
) {
  if (!series || series.length < 2) return null;
  const W = 600,
    H = 240;
  const padL = 48,
    padR = 24,
    padT = 20,
    padB = 36;
  const w = W - padL - padR;
  const h = H - padT - padB;

  const values = series.map((s) => s.value);
  const vmin = Math.min(...values);
  const vmax = Math.max(...values);
  const vpad = (vmax - vmin) * 0.12 || 1;
  const ymin = vmin - vpad;
  const ymax = vmax + vpad;

  const pts = series.map((s, i) => {
    const x = padL + (i / (series.length - 1)) * w;
    const y = padT + (1 - (s.value - ymin) / (ymax - ymin)) * h;
    return { x, y, period: s.period, value: s.value };
  });

  let d = `M ${pts[0].x.toFixed(2)} ${pts[0].y.toFixed(2)}`;
  for (let i = 1; i < pts.length; i++) {
    const p0 = pts[i - 2] || pts[i - 1];
    const p1 = pts[i - 1],
      p2 = pts[i],
      p3 = pts[i + 1] || pts[i];
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)}, ${cp2x.toFixed(2)} ${cp2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
  }
  const areaD =
    d +
    ` L ${pts[pts.length - 1].x.toFixed(2)} ${(padT + h).toFixed(2)}` +
    ` L ${pts[0].x.toFixed(2)} ${(padT + h).toFixed(2)} Z`;

  const xTicks = series
    .map((s, i) => ({ i, period: s.period }))
    .filter((_, i) => i % Math.max(1, Math.floor(series.length / 6)) === 0 || i === series.length - 1);
  const yTicks = [0, 0.5, 1].map((f) => {
    const v = ymin + (ymax - ymin) * (1 - f);
    const y = padT + f * h;
    return { y, v };
  });

  const first = series[0].value;
  const last = series[series.length - 1].value;
  const deltaPct = ((last - first) / first) * 100;

  return {
    W, H, padL, padR, padT, padB, w, h,
    pts, d, areaD, xTicks, yTicks,
    stroke, unit,
    current: last,
    deltaPct,
    first, last,
    periodStart: series[0].period,
    periodEnd: series[series.length - 1].period,
  };
}

// ────────────────────────────────────────────────────────────────────────
// 60-month balance chart
// ────────────────────────────────────────────────────────────────────────

export type BalanceSpec = ReturnType<typeof buildBalanceChart>;

export function buildBalanceChart(series: BalancePoint[] | null | undefined) {
  if (!series || series.length < 2) return null;
  const W = 960,
    H = 340;
  const padL = 56,
    padR = 24,
    padT = 28,
    padB = 40;
  const w = W - padL - padR;
  const h = H - padT - padB;

  const values = series.map((s) => s.value_eur_bn);
  const vmin = Math.min(...values, 0);
  const vmax = Math.max(...values, 0);
  const vpad = (vmax - vmin) * 0.1 || 1;
  const ymin = vmin - vpad;
  const ymax = vmax + vpad;

  const yScale = (v: number) => padT + (1 - (v - ymin) / (ymax - ymin)) * h;
  const xScale = (i: number) => padL + (i / (series.length - 1)) * w;
  const zeroY = yScale(0);

  const pts = series.map((s, i) => ({
    x: xScale(i),
    y: yScale(s.value_eur_bn),
    period: s.period,
    value: s.value_eur_bn,
  }));

  let d = `M ${pts[0].x.toFixed(2)} ${pts[0].y.toFixed(2)}`;
  for (let i = 1; i < pts.length; i++) {
    const p0 = pts[i - 2] || pts[i - 1];
    const p1 = pts[i - 1],
      p2 = pts[i],
      p3 = pts[i + 1] || pts[i];
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)}, ${cp2x.toFixed(2)} ${cp2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
  }

  const xTicks = series
    .map((s, i) => ({ i, period: s.period }))
    .filter((_, i) => i === 0 || i === series.length - 1 || i % 12 === 0);
  const yTicksVals = [ymin, (ymin + ymax) / 2, 0, ymax].filter((v) => v >= ymin && v <= ymax);
  const yTicks = Array.from(new Set(yTicksVals.map((v) => Math.round(v * 10) / 10)))
    .sort((a, b) => a - b)
    .map((v) => ({ v, y: yScale(v) }));

  return { W, H, padL, padR, padT, padB, w, h, pts, d, zeroY, xTicks, yTicks, yScale, xScale };
}

// ────────────────────────────────────────────────────────────────────────
// 60-month partners chart
// ────────────────────────────────────────────────────────────────────────

export type PartnersSpec = ReturnType<typeof buildPartnersChart>;
type PartnerSeriesMap = Record<string, BalancePoint[]>;

export function buildPartnersChart(
  series_by: PartnerSeriesMap | null | undefined,
  currentMonth: string,
) {
  if (!series_by || !series_by.US) return null;
  const partners = [
    { code: 'US', label: 'United States', color: '#F47B20', weight: 2.2 },
    { code: 'GB', label: 'United Kingdom', color: '#005CAB', weight: 1.3 },
    { code: 'CN', label: 'China', color: '#00A99E', weight: 1.3 },
    { code: 'CH', label: 'Switzerland', color: '#79B777', weight: 1.1 },
    { code: 'OTHER', label: 'Other', color: '#aaaaaa', weight: 1.0 },
  ];
  const first = series_by.US;
  if (!first || first.length < 2) return null;

  const W = 960,
    H = 380;
  const padL = 56,
    padR = 24,
    padT = 40,
    padB = 44;
  const w = W - padL - padR;
  const h = H - padT - padB;

  const allValues = partners.flatMap((p) => (series_by[p.code] || []).map((s) => s.value_eur_bn));
  const vmin = 0;
  const vmax = Math.max(...allValues);
  const vpad = vmax * 0.08 || 1;
  const ymax = vmax + vpad;

  const yScale = (v: number) => padT + (1 - (v - vmin) / (ymax - vmin)) * h;
  const xScale = (i: number) => padL + (i / (first.length - 1)) * w;

  const seriesData = partners.map((p) => {
    const data = series_by[p.code] || [];
    if (data.length < 2) return { ...p, pts: [], d: '', current: undefined };
    const pts = data.map((s, i) => ({
      x: xScale(i),
      y: yScale(s.value_eur_bn),
      period: s.period,
      value: s.value_eur_bn,
    }));
    let d = `M ${pts[0].x.toFixed(2)} ${pts[0].y.toFixed(2)}`;
    for (let i = 1; i < pts.length; i++) {
      const p0 = pts[i - 2] || pts[i - 1];
      const p1 = pts[i - 1],
        p2 = pts[i],
        p3 = pts[i + 1] || pts[i];
      const cp1x = p1.x + (p2.x - p0.x) / 6;
      const cp1y = p1.y + (p2.y - p0.y) / 6;
      const cp2x = p2.x - (p3.x - p1.x) / 6;
      const cp2y = p2.y - (p3.y - p1.y) / 6;
      d += ` C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)}, ${cp2x.toFixed(2)} ${cp2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
    }
    const current = pts.find((pt) => pt.period === currentMonth);
    return { ...p, pts, d, current };
  });

  const xTicks = first
    .map((s, i) => ({ i, period: s.period }))
    .filter((_, i) => i === 0 || i === first.length - 1 || i % 12 === 0);
  const yTicks = [0, ymax * 0.25, ymax * 0.5, ymax * 0.75, ymax].map((v) => ({ v, y: yScale(v) }));

  return {
    W, H, padL, padR, padT, padB, w, h,
    partners: seriesData,
    xTicks, yTicks,
    periods: first.length,
  };
}

// ────────────────────────────────────────────────────────────────────────
// Inline waterfall (per-partner CN8 drill-down)
// ────────────────────────────────────────────────────────────────────────

type Mover = { cn8: string; label: string; delta_eur_bn: number; delta_pct?: number | null };

export type WaterfallSpec = ReturnType<typeof buildWaterfall>;

export function buildWaterfall(info: any) {
  if (!info || info.skipped) return null;
  const start = Number(info.period_a_value_eur_bn || 0);
  const end = Number(info.period_b_value_eur_bn || 0);
  const ups = (info.top_movers_up || []).slice(0, 3) as Mover[];
  const downs = (info.top_movers_down || []).slice(0, 3) as Mover[];
  const listedDelta = [...ups, ...downs].reduce((s, m) => s + Number(m.delta_eur_bn || 0), 0);
  const totalDelta = end - start;
  const otherDelta = totalDelta - listedDelta;

  type Bar = {
    kind: 'start' | 'up' | 'down' | 'other' | 'end';
    label: string;
    short?: string;
    value?: number;
    delta?: number;
    cumulative: number;
    color: string;
  };
  const bars: Bar[] = [];
  let running = start;
  bars.push({ kind: 'start', label: 'Previous year', short: 'Prev. year',
              value: start, cumulative: start, color: '#007DC3' });
  for (const m of ups) {
    running += m.delta_eur_bn;
    bars.push({ kind: 'up', label: m.label, short: m.label, delta: m.delta_eur_bn,
                cumulative: running, color: '#00A99E' });
  }
  if (Math.abs(otherDelta) > 0.01) {
    running += otherDelta;
    bars.push({ kind: 'other', label: 'Other products', short: 'Other', delta: otherDelta,
                cumulative: running, color: '#8a8a8a' });
  }
  for (const m of downs) {
    running += m.delta_eur_bn;
    bars.push({ kind: 'down', label: m.label, short: m.label, delta: m.delta_eur_bn,
                cumulative: running, color: '#F47B20' });
  }
  bars.push({ kind: 'end', label: 'Current', short: 'Current',
              value: end, cumulative: end, color: '#005CAB' });

  const W = 760,
    H = 380,
    padL = 56,
    padR = 24,
    padT = 28,
    padB = 110;
  const w = W - padL - padR,
    h = H - padT - padB;
  const values = bars.flatMap((b, i) => {
    if (b.kind === 'start' || b.kind === 'end') return [0, b.value || 0];
    const prev = i === 0 ? 0 : bars[i - 1].cumulative;
    return [prev, b.cumulative];
  });
  const ymax = Math.max(...values) * 1.08;
  const ymin = Math.min(0, ...values);
  const yScale = (v: number) => padT + (1 - (v - ymin) / (ymax - ymin)) * h;
  const zeroY = yScale(0);

  const gap = 0.2;
  const slot = w / bars.length;
  const bw = slot * (1 - gap);

  const rects = bars.map((b, i) => {
    const cx = padL + slot * (i + 0.5);
    const x = cx - bw / 2;
    let yTop: number, yBot: number;
    if (b.kind === 'start' || b.kind === 'end') {
      yTop = yScale(b.value || 0);
      yBot = zeroY;
    } else {
      const prev = i === 0 ? 0 : bars[i - 1].cumulative;
      yTop = yScale(Math.max(prev, b.cumulative));
      yBot = yScale(Math.min(prev, b.cumulative));
    }
    const y = Math.min(yTop, yBot);
    const height = Math.abs(yBot - yTop);
    return { ...b, i, cx, x, y, width: bw, height, yTop, yBot };
  });

  return { W, H, padL, padR, padT, padB, w, h, bars: rects, yScale, zeroY, totalDelta };
}

// ────────────────────────────────────────────────────────────────────────
// KPI cards (from macro_brief fiche)
// ────────────────────────────────────────────────────────────────────────

function buildKpis(macroFiche: any): Kpi[] {
  if (macroFiche && macroFiche.kpi_cards) {
    return macroFiche.kpi_cards.map((k: any) => ({
      label: k.label,
      value: k.value_formatted || k.value,
      delta: k.yoy_formatted || k.yoy || '',
      dir: k.yoy && Number(k.yoy) > 0 ? 'pos' : 'neg',
      foot: k.footnote || k.period || '',
    }));
  }
  return [];
}

// ────────────────────────────────────────────────────────────────────────
// Partner cards (US / CN / GB)
// ────────────────────────────────────────────────────────────────────────

const STRUCTURAL_PARTNERS: Array<{ code: string; label: string }> = [
  { code: 'US', label: 'United States' },
  { code: 'CN', label: 'China' },
  { code: 'GB', label: 'United Kingdom' },
];

function buildPartnerCards(tradeExports: any): PartnerCard[] {
  if (!tradeExports?.data?.by_partner) return [];
  const byCode: Record<string, any> = {};
  for (const p of tradeExports.data.by_partner) {
    if (p.partner) byCode[p.partner] = p;
  }
  const cards: PartnerCard[] = [];
  for (const sp of STRUCTURAL_PARTNERS) {
    const p = byCode[sp.code];
    if (!p) continue;
    const delta = Number((p.value_eur_bn - p.previous_year_value_eur_bn).toFixed(2));
    cards.push({
      code: sp.code,
      label: sp.label,
      value_now: `€${p.value_eur_bn.toFixed(2)} bn`,
      delta_value: `${delta >= 0 ? '+' : ''}${delta.toFixed(2)} bn`,
      yoy_pct: `${p.yoy_pct >= 0 ? '+' : ''}${p.yoy_pct.toFixed(1)}%`,
      dir: p.yoy_pct >= 0 ? 'pos' : 'neg',
      share_pct: `${p.share_pct.toFixed(1)}%`,
      top_chapters: (p.top_nace || []).slice(0, 3).map((c: any) => {
        const hasYoy = c.yoy_pct !== undefined && c.yoy_pct !== null && c.yoy_pct !== 0;
        return {
          label: (c.label || '').split(',')[0].slice(0, 40),
          yoy_pct: hasYoy ? `${c.yoy_pct >= 0 ? '+' : ''}${c.yoy_pct.toFixed(1)}%` : '',
          value_now: `€${(c.value_eur_bn ?? 0).toFixed(2)} bn`,
        };
      }),
    });
  }
  return cards;
}

// ────────────────────────────────────────────────────────────────────────
// Aggregator
// ────────────────────────────────────────────────────────────────────────

export type EditionData = {
  entry: CollectionEntry<'editions'>;
  monthName: string;
  monthShort: string;
  // Sections
  mdxSections: MdxSection[];
  headlineSection: MdxSection | null;
  macroProseSections: MdxSection[];
  tradeProseSections: MdxSection[];
  trajectorySection: MdxSection | null;
  concentrationSection: MdxSection | null;
  // Titles
  overviewTitle: string;
  macroTitle: string;
  drilldownTitle: string;
  // Data
  kpis: Kpi[];
  partnerCards: PartnerCard[];
  countryPerf: Array<{ label: string; value: number }>;
  maxMag: number;
  // Charts
  outputSpark: SparkSpec;
  pricesSpark: SparkSpec;
  salesSpark: SparkSpec;
  balance60m: BalanceSpec;
  partners60m: PartnersSpec;
  waterfallUsImp: WaterfallSpec;
  waterfallCnImp: WaterfallSpec;
  // PDF download (kept here so any layout can decide what to do)
  pdfUrl: string;
  pdfName: string;
  pdfExists: boolean;
};

export function loadEditionData(entry: CollectionEntry<'editions'>): EditionData {
  const id = entry.id;
  const tradeExports = readFiche(id, 'trade_exports');
  const tradeImports = readFiche(id, 'trade_imports');
  const macroFiche = readFiche(id, 'macro_brief');
  const outputFiche = readFiche(id, 'output');
  const pricesFiche = readFiche(id, 'prices');
  const salesFiche = readFiche(id, 'sales');

  const mdxSections = parseMdxSections(entry.body);
  const sectionHeadings = mdxSections.map((s) => s.title);

  const headlineSection = mdxSections[0] ?? null;
  const macroProseSections = [mdxSections[1], mdxSections[2], mdxSections[3]].filter(
    (s): s is MdxSection => Boolean(s),
  );
  const tradeProseSections = [mdxSections[4], mdxSections[5]].filter(
    (s): s is MdxSection => Boolean(s),
  );
  const trajectorySection =
    mdxSections.find((s) => /trajectory|six years on/i.test(s.title)) ?? null;
  const concentrationSection =
    mdxSections.find((s) => /concentration|strategic exposure/i.test(s.title)) ?? null;

  const outputSpark = buildSpark(outputFiche?.data?.monthly_series, '#F47B20', 'Index (2021=100)');
  const pricesSpark = buildSpark(pricesFiche?.data?.monthly_series, '#005CAB', 'Index (2021=100)');
  const salesSpark = buildSpark(salesFiche?.data?.monthly_series, '#00A99E', 'Index (2021=100)');

  const balance60m = buildBalanceChart(tradeExports?.data?.historical_series?.trade_balance_monthly);
  const partners60m = buildPartnersChart(
    tradeExports?.data?.historical_series?.exports_by_partner_monthly,
    id,
  );
  const waterfallUsImp = buildWaterfall(tradeImports?.data?.partner_drilldown?.US);
  const waterfallCnImp = buildWaterfall(tradeImports?.data?.partner_drilldown?.CN);

  const partnerCards = buildPartnerCards(tradeExports);

  // Country YoY: hardcoded ordering for now (the macro fiche has the data
  // but no canonical ordering; keep as-is until we wire the fiche).
  const countryPerf = [
    { label: 'Netherlands', value: -9.6 },
    { label: 'Italy', value: -6.9 },
    { label: 'Germany', value: -3.5 },
    { label: 'Spain', value: -3.3 },
    { label: 'Poland', value: -2.1 },
    { label: 'Belgium', value: -1.2 },
    { label: 'France', value: 1.1 },
  ];
  const maxMag = Math.max(...countryPerf.map((c) => Math.abs(c.value)));

  // PDF (always present in CI; existence-checked here for local dev).
  const pdfRelPath = `public/downloads/${id}.pdf`;
  let pdfExists = false;
  try {
    pdfExists = fs.statSync(pdfRelPath).isFile();
  } catch {
    /* not generated yet */
  }
  const pdfUrl = `/downloads/${id}.pdf`;
  const pdfName = `Iris-${monthName(id).replace(' ', '-')}.pdf`;

  return {
    entry,
    monthName: monthName(id),
    monthShort: monthShort(id),
    mdxSections,
    headlineSection,
    macroProseSections,
    tradeProseSections,
    trajectorySection,
    concentrationSection,
    overviewTitle: sectionHeadings[0] ?? `Overview, ${monthName(id)}`,
    macroTitle: sectionHeadings[1] ?? `Macro brief, ${monthName(id)}`,
    drilldownTitle: sectionHeadings[4] ?? `Drill-down, ${monthName(id)}`,
    kpis: buildKpis(macroFiche),
    partnerCards,
    countryPerf,
    maxMag,
    outputSpark,
    pricesSpark,
    salesSpark,
    balance60m,
    partners60m,
    waterfallUsImp,
    waterfallCnImp,
    pdfUrl,
    pdfName,
    pdfExists,
  };
}
