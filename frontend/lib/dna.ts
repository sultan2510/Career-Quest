import { DNA_SCENARIOS } from '@/lib/data/dna';
import type { DimKey, DnaScenario, DnaState } from '@/lib/dna-types';

type Dim = { label: string; max: number; weight: number; blurb: string };
// weight comes from the questionnaire's scoring table ("creative" is not in it, so 1.0 is our assumption). max is the table's stated
// maximum, kept for reference only: the questions cannot actually reach it for several dimensions, so scores use the points available instead.
export const DIMS: Record<DimKey, Dim> = {
  logical: { label: 'Logical-Mathematical', max: 50, weight: 1.2, blurb: 'I reason step by step and trust evidence and structure.' },
  spatial: { label: 'Spatial-Visual', max: 45, weight: 1.1, blurb: 'I think in shapes, maps and mental pictures.' },
  verbal: { label: 'Verbal-Linguistic', max: 40, weight: 1.0, blurb: 'I think best through words, explanations and stories.' },
  inter: { label: 'Interpersonal', max: 45, weight: 1.15, blurb: 'I read people well and do my best work with others.' },
  intra: { label: 'Intrapersonal', max: 40, weight: 1.1, blurb: 'I know my own motives and reflect before I act.' },
  bodily: { label: 'Bodily-Kinesthetic', max: 25, weight: 0.9, blurb: 'I learn by doing, moving and handling things.' },
  musical: { label: 'Musical', max: 15, weight: 0.8, blurb: 'I notice rhythm, sound and pattern over time.' },
  naturalistic: { label: 'Naturalistic', max: 25, weight: 0.9, blurb: 'I spot patterns in living and complex systems.' },
  existential: { label: 'Existential', max: 20, weight: 0.85, blurb: 'I keep asking why, about meaning and purpose.' },
  fluid: { label: 'Fluid Intelligence', max: 50, weight: 1.3, blurb: 'I work out brand-new problems without a rulebook.' },
  learning: { label: 'Learning Ability', max: 30, weight: 1.2, blurb: 'I pick up new systems fast and transfer what I learn.' },
  adapt: { label: 'Career Adaptability', max: 25, weight: 1.1, blurb: 'I plan, explore and bounce back when things change.' },
  creative: { label: 'Creative Intelligence', max: 30, weight: 1.0, blurb: 'I generate original ideas and unexpected angles.' },
};
export const DIM_KEYS = Object.keys(DIMS) as DimKey[];

/** The questionnaire's reconciliation scenario for inconsistent social answers. The score nudges are our assumption. */
export const RECON: { text: string; effect: Partial<Record<DimKey, number>> }[] = [
  { text: 'I understand others well but find social interaction draining.', effect: { inter: 2, intra: 2 } },
  { text: 'I am good with people but trust my own judgment more.', effect: { intra: 3 } },
  { text: 'My social skills are situational: I perform well under pressure but not in casual settings.', effect: { adapt: 3 } },
];

/** Dimension a branch deepens; used for the Branching Depth score. */
export const BRANCH_DIM: Record<string, DimKey> = { '1.1A': 'spatial', '1.1C': 'inter', '2.1A': 'logical', '3.1B': 'inter', '4.2': 'learning' };

export const FAMILIES: { name: string; riasec: string; high: DimKey[]; low?: DimKey[] }[] = [
  { name: 'Engineering, Architecture, Data Science', riasec: 'Realistic-Investigative', high: ['spatial', 'logical'], low: ['inter'] },
  { name: 'Counseling, Human Resources, Education', riasec: 'Social-Enterprising', high: ['inter', 'verbal', 'intra'] },
  { name: 'Industrial Design, Surgery, Filmmaking', riasec: 'Artistic-Realistic', high: ['spatial', 'bodily', 'creative'] },
  { name: 'Research Management, Consulting, Medicine', riasec: 'Investigative-Social', high: ['logical', 'inter', 'learning'] },
  { name: 'Philosophy, Writing, Psychotherapy', riasec: 'Artistic-Social', high: ['existential', 'verbal', 'intra'] },
];

const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);

export function nextScenario(answers: Record<string, string>): DnaScenario | null {
  for (const s of DNA_SCENARIOS) {
    if (s.id in answers) continue;
    if (s.parent && answers[s.parent] !== s.option) continue; // branch not triggered
    return s;
  }
  return null;
}

export function rawScores(st: DnaState): Record<DimKey, number> {
  const out = Object.fromEntries(DIM_KEYS.map(k => [k, 0])) as Record<DimKey, number>;
  for (const s of DNA_SCENARIOS) for (const [d, v] of Object.entries(s.scores[st.answers[s.id]] ?? {})) out[d as DimKey] += v as number;
  if (st.tie) out[st.tie] += 3;
  if (st.recon !== null) for (const [d, v] of Object.entries(RECON[st.recon].effect)) out[d as DimKey] += v as number;
  return out;
}

export type DimResult = { key: DimKey; raw: number; norm: number; weighted: number; asked: number };
export function profile(st: DnaState): DimResult[] {
  const raw = rawScores(st);
  // Score each dimension against the points the user could have earned on the scenarios they actually answered.
  const possible = Object.fromEntries(DIM_KEYS.map(k => [k, 0])) as Record<DimKey, number>;
  const asked = { ...possible };
  for (const s of DNA_SCENARIOS) if (s.id in st.answers) for (const k of DIM_KEYS) {
    const best = Math.max(...Object.values(s.scores).map(r => r[k] ?? 0));
    if (best > 0) { possible[k] += best; asked[k] += 1; }
  }
  return DIM_KEYS.map(key => { const norm = possible[key] ? Math.min(1, raw[key] / possible[key]) : 0; return { key, raw: raw[key], norm, weighted: norm * DIMS[key].weight, asked: asked[key] }; })
    .sort((a, b) => b.weighted - a.weighted);
}

/** Ambiguous branching: close top-two scores, or social answers that contradict each other. */
export function ambiguity(st: DnaState) {
  const p = profile(st);
  const tie = p[0].weighted - p[1].weighted < 0.05 ? ([p[0].key, p[1].key] as [DimKey, DimKey]) : null;
  const inter = (parts: number[]) => DNA_SCENARIOS.filter(s => parts.includes(s.part)).reduce((n, s) => n + (s.scores[st.answers[s.id]]?.inter ?? 0), 0);
  return { tie, inconsistent: inter([3]) >= 8 && inter([1, 6]) <= 3 };
}

export type Stage = { kind: 'scenario'; s: DnaScenario } | { kind: 'recon' } | { kind: 'tie'; a: DimKey; b: DimKey } | { kind: 'done' };
export function stageOf(st: DnaState): Stage {
  const s = nextScenario(st.answers);
  if (s) return { kind: 'scenario', s };
  const amb = ambiguity(st);
  if (amb.inconsistent && st.recon === null) return { kind: 'recon' };
  if (amb.tie && st.tie === null) return { kind: 'tie', a: amb.tie[0], b: amb.tie[1] };
  return { kind: 'done' };
}

export function careerFit(st: DnaState) {
  const norm = Object.fromEntries(profile(st).map(r => [r.key, r.norm])) as Record<DimKey, number>;
  return FAMILIES.map(f => ({ ...f, fit: Math.max(0, Math.min(1, mean(f.high.map(k => norm[k])) - 0.5 * mean((f.low ?? []).map(k => norm[k])))) }))
    .sort((a, b) => b.fit - a.fit);
}

export const RIASEC_NAMES: Record<string, string> = {
  R: 'Realistic', I: 'Investigative', A: 'Artistic', S: 'Social', E: 'Enterprising', C: 'Conventional',
};

/**
 * Holland code, built only from the source document's own pattern-to-RIASEC alignments: each matched
 * career family contributes its two letters, weighted by how well that family fits. Nothing is mapped
 * dimension-to-letter by hand. Note the consequence — Conventional never appears in any of the five
 * alignments, so no run can produce a C.
 */
export function riasecProfile(st: DnaState) {
  const tally: Record<string, number> = { R: 0, I: 0, A: 0, S: 0, E: 0, C: 0 };
  for (const f of careerFit(st)) for (const name of f.riasec.split('-')) {
    const letter = name[0].toUpperCase();
    if (letter in tally) tally[letter] += f.fit;
  }
  const max = Math.max(...Object.values(tally));
  const ranked = Object.keys(tally)
    .map(letter => ({ letter, name: RIASEC_NAMES[letter], score: tally[letter], norm: max ? tally[letter] / max : 0 }))
    .sort((a, b) => b.score - a.score);
  return { code: max ? ranked.slice(0, 3).map(r => r.letter).join('') : '', ranked, assessed: max > 0 };
}

export function depth(st: DnaState) {  const reached = DNA_SCENARIOS.filter(s => s.parent && s.id in st.answers).map(s => BRANCH_DIM[s.id]);
  return { reached: reached.length, total: Object.keys(BRANCH_DIM).length, byDim: reached.reduce<Partial<Record<DimKey, number>>>((m, d) => ({ ...m, [d]: (m[d] ?? 0) + 1 }), {}) };
}

/** One-line summary sent to the mentor so answers are personal. */
export function summary(st: DnaState) {
  if (!Object.keys(st.answers).length) return '';
  const top = profile(st).slice(0, 5).map(r => `${DIMS[r.key].label} ${Math.round(r.norm * 100)}%`).join(', ');
  return `Top strengths: ${top}. Best career-family fits: ${careerFit(st).slice(0, 3).map(f => f.name).join('; ')}.`;
}
