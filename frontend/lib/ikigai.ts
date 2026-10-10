import snapshot from '@/lib/data/occupation-evidence.json';
import { profile } from '@/lib/dna';
import { interestScores, RIASEC } from '@/lib/interests';
import type { Progress } from '@/lib/types';

export const CIRCLES = ['love', 'good', 'needs', 'paid'] as const;
export type Circle = (typeof CIRCLES)[number];
export type CircleScores = Record<Circle, number | null>;
type Occupation = (typeof snapshot.occupations)[keyof typeof snapshot.occupations];
export const EVIDENCE = snapshot;

const clamp = (x: number) => Math.max(0, Math.min(1, x));
const pct = (value: number | null, values: (number | null)[]) => {
  if (value === null || !Number.isFinite(value)) return null;
  const valid = values.filter((v): v is number => v !== null && Number.isFinite(v));
  if (valid.length < 2) return null;
  return (valid.filter(v => v < value).length + valid.filter(v => v === value).length / 2 - 0.5) / (valid.length - 1);
};
const avg = (xs: number[]) => xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
const weighted = (xs: [number, number][]) => xs.length ? xs.reduce((a, [v, w]) => a + v * w, 0) / xs.reduce((a, [, w]) => a + w, 0) : null;

const entries = Object.entries(snapshot.occupations) as [string, Occupation][];
const usGrowth = entries.map(([, o]) => o.us.growth_pct);
const usOpenings = entries.map(([, o]) => o.us.annual_openings);
const usWage = entries.map(([, o]) => o.us.median_annual_usd);
const pkEmployment = entries.map(([, o]) => o.pk.employment_thousands_2025);
const pkGrowth = entries.map(([, o]) => (o.pk.employment_thousands_2025 - o.pk.employment_thousands_2021) / o.pk.employment_thousands_2021);
const pkWage = Object.values(snapshot.pk_earnings_major_groups_2025);

export type IkigaiCareer = { id: string; scores: CircleScores; overall: number | null; occupation: Occupation; count: number };

/** Independent, opt-in evidence layer. No mutation of the existing recommender. */
export function ikigaiCareers(progress: Progress): IkigaiCareer[] {
  const answers = interestScores(progress.interests);
  const dims = profile(progress.dna).filter(d => d.asked > 0);
  return entries.map(([id, occupation]) => {
    const interestParts = RIASEC.filter(k => answers[k] !== undefined).map(k => [answers[k]!, occupation.interests[k]] as [number, number]);
    const interestFit = weighted(interestParts);
    const skillParts = dims.filter(d => d.key in occupation.requirements).map(d => {
      // A few answers are not strong evidence. Three pseudo-observations shrink toward 0.5.
      const shrunk = (d.norm * d.asked + 0.5 * 3) / (d.asked + 3);
      return [shrunk, occupation.requirements[d.key as keyof typeof occupation.requirements]] as [number, number];
    });
    const skillFit = weighted(skillParts);
    const sim = progress.evidence.filter(e => e.careerId === id);
    const enjoyment = avg(sim.map(e => (e.enjoyment - 1) / 4));
    const confidence = avg(sim.map(e => (e.confidence - 1) / 4));
    const love = interestFit === null ? enjoyment : enjoyment === null ? interestFit : 0.8 * interestFit + 0.2 * enjoyment;
    const good = skillFit === null ? confidence : confidence === null ? skillFit : 0.8 * skillFit + 0.2 * confidence;
    const needs = progress.country === 'US'
      ? avg([pct(occupation.us.growth_pct, usGrowth), pct(occupation.us.annual_openings, usOpenings)].filter((v): v is number => v !== null))
      : avg([pct((occupation.pk.employment_thousands_2025 - occupation.pk.employment_thousands_2021) / occupation.pk.employment_thousands_2021, pkGrowth), pct(occupation.pk.employment_thousands_2025, pkEmployment)].filter((v): v is number => v !== null));
    const paid = progress.country === 'US' ? pct(occupation.us.median_annual_usd, usWage) : pct(occupation.pk.median_hourly_pkr_2025_major_group, pkWage);
    const scores: CircleScores = { love, good, needs, paid };
    const available = CIRCLES.filter(k => scores[k] !== null);
    // Four-circle summary only exists when all four signals exist.
    const overall = available.length === 4 ? Math.exp(CIRCLES.reduce((s, k) => s + Math.log(Math.max(scores[k]!, 0.02)), 0) / 4) : null;
    return { id, scores, overall: overall === null ? null : clamp(overall), occupation, count: available.length };
  }).sort((a, b) => (b.overall ?? -1) - (a.overall ?? -1));
}
