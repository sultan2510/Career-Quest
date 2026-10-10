import { CAREERS, careerById } from '@/lib/data/careers';
import { CHARACTERS } from '@/lib/data/characters';
import { TRAITS, type Career, type Evidence, type Progress, type Quality, type Trait } from '@/lib/types';

const clamp = (n: number) => Math.max(0, Math.min(100, Math.round(n)));

/** Trait values (0–98). The character choice seeds them; simulation evidence refines the fit from there. */
export function traitValues(character: number | null): Record<Trait, number> {
  const raw = Object.fromEntries(TRAITS.map(t => [t, 0])) as Record<Trait, number>;
  const seed = character !== null ? CHARACTERS[character]?.seed : undefined;
  if (seed) for (const t of TRAITS) raw[t] += seed[t] ?? 0;
  return Object.fromEntries(TRAITS.map(t => [t, Math.min(98, 50 + raw[t] * 4)])) as Record<Trait, number>;
}

export function dominantTraits(traits: Record<Trait, number>, count = 2): Trait[] {
  return [...TRAITS].sort((a, b) => traits[b] - traits[a]).slice(0, count);
}

function traitFit(career: Career, traits: Record<Trait, number>) {
  let num = 0;
  let den = 0;
  for (const t of TRAITS) {
    const w = career.profile[t] ?? 0;
    num += traits[t] * w;
    den += w;
  }
  return den ? num / den : 50;
}

export const averageQuality = (ev: Evidence): number | null => {
  const scored = ev.decisions.filter(d => d.quality !== null) as { quality: Quality }[];
  return scored.length ? scored.reduce((sum, d) => sum + d.quality, 0) / scored.length : null;
};

export type FitBreakdown = { love: number; goodAt: number; needs: number; paid: number; overall: number };

/**
 * Ikigai-style score. "Love" starts from trait fit and moves with enjoyment ratings.
 * "Good at" starts near neutral (we have no skill evidence yet) and moves with confidence and decision quality.
 * "World needs" and "paid" are static, illustrative career attributes.
 */
export function scoreCareer(career: Career, traits: Record<Trait, number>, evidence: Evidence[]): FitBreakdown {
  const fit = traitFit(career, traits);
  let love = fit;
  let goodAt = 60 + (fit - 60) * 0.5;
  for (const ev of evidence) {
    const delta = (ev.enjoyment - 3) * 7;
    if (ev.careerId === career.id) {
      love += delta;
      goodAt += (ev.confidence - 3) * 3;
      const q = averageQuality(ev);
      if (q !== null) goodAt += (q - 1) * 10;
    } else {
      // Cross-career preference transfer: a small nudge for careers that share themes.
      const other = careerById(ev.careerId);
      const shared = other ? other.tags.filter(t => career.tags.includes(t)).length : 0;
      love += delta * 0.12 * shared;
    }
  }
  love = clamp(love);
  goodAt = clamp(goodAt);
  const overall = clamp(0.35 * love + 0.25 * goodAt + 0.2 * career.needs + 0.2 * career.paid);
  return { love, goodAt, needs: career.needs, paid: career.paid, overall };
}

export type Ranked = { career: Career; score: FitBreakdown; baseline: FitBreakdown; delta: number };

export function rankCareers(traits: Record<Trait, number>, evidence: Evidence[]): Ranked[] {
  return CAREERS.map(career => {
    const score = scoreCareer(career, traits, evidence);
    const baseline = scoreCareer(career, traits, []);
    return { career, score, baseline, delta: score.overall - baseline.overall };
  }).sort((a, b) => b.score.overall - a.score.overall);
}

/** A career that differs from the student's strongest trait but still scores well. */
export function surpriseCareer(ranked: Ranked[], traits: Record<Trait, number>): Ranked {
  const [top] = dominantTraits(traits, 1);
  const different = ranked.filter(r => (r.career.profile[top as Trait] ?? 0) < 2);
  return different[0] ?? ranked[ranked.length - 1]!;
}

/** Separates what someone enjoys from what they felt able to do. */
export function classifyEvidence(ev: Evidence): { label: string; note: string } {
  const enjoys = ev.enjoyment >= 4;
  const unsure = ev.enjoyment <= 2;
  const confident = ev.confidence >= 4;
  const lowConf = ev.confidence <= 2;
  if (enjoys && confident) return { label: 'Energizing strength', note: 'You enjoyed it and felt capable. A strong signal to keep exploring.' };
  if (enjoys && lowConf) return { label: 'Interest to build', note: 'You liked it but felt unsure. Skills can grow, so a small project may help.' };
  if (unsure && confident) return { label: 'Skill, not a spark', note: 'You felt capable but it didn’t energize you. Being able to do something isn’t the same as wanting to.' };
  if (unsure && lowConf) return { label: 'Not a fit for now', note: 'It felt draining and uncertain. That’s useful to know, not a failure.' };
  return { label: 'Mixed signal', note: 'A neutral reaction. Another scenario or a real conversation could add clarity.' };
}

export const LEVELS = ['Sprout', 'Seeker', 'Trailblazer', 'Pathfinder', 'Navigator', 'Trailmaster'];
const XP_PER_LEVEL = 200;

/** What one completed roadmap step is worth. Shown on the step itself, so keep the number in one place. */
export const XP_PER_TASK = 10;

export function computeXp(p: Progress): number {
  const taskCount = Object.values(p.tasks).reduce((n, list) => n + list.length, 0);
  return (p.character !== null ? 50 : 0) + p.evidence.length * 100 + taskCount * XP_PER_TASK + p.journal.length * 30 + p.explored.length * 5;
}

export function levelInfo(xp: number) {
  const level = Math.floor(xp / XP_PER_LEVEL) + 1;
  return {
    level,
    title: LEVELS[Math.min(level - 1, LEVELS.length - 1)]!,
    intoLevel: xp % XP_PER_LEVEL,
    perLevel: XP_PER_LEVEL,
  };
}

export type Badge = { id: string; name: string; hint: string; earned: boolean };

export function computeBadges(p: Progress): Badge[] {
  const taskCount = Object.values(p.tasks).reduce((n, list) => n + list.length, 0);
  const fullRoadmap = Object.values(p.tasks).some(list => list.length >= 12);
  return [
    { id: 'character', name: 'First steps', hint: 'Choose your character', earned: p.character !== null },
    { id: 'curious', name: 'Curious mind', hint: 'Look closely at 3 careers', earned: p.explored.length >= 3 },
    { id: 'simulate', name: 'First day on the job', hint: 'Complete a day in the life', earned: p.evidence.length >= 1 },
    { id: 'range', name: 'Wide lens', hint: 'Try 3 different careers', earned: new Set(p.evidence.map(e => e.careerId)).size >= 3 },
    { id: 'journal', name: 'Reflective', hint: 'Write a journal entry', earned: p.journal.length >= 1 },
    { id: 'planner', name: 'Making moves', hint: 'Complete a roadmap step', earned: taskCount >= 1 },
    { id: 'finisher', name: 'Roadmap finisher', hint: 'Finish all 12 roadmap steps', earned: fullRoadmap },
  ];
}
