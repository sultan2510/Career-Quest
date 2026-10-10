'use client';
import { createContext, useContext, useEffect, useMemo, useReducer, useRef, useState, type Dispatch, type ReactNode } from 'react';
import { loadProgress, saveProgress } from '@/lib/storage';
import { createSaveQueue } from '@/lib/save-queue';
import { stageOf } from '@/lib/dna';
import { computeBadges, computeXp, levelInfo, rankCareers, traitValues, type Badge, type Ranked } from '@/lib/scoring';
import { emptyProgress, type Evidence, type JournalEntry, type Progress, type Trait } from '@/lib/types';

type Action =
  | { type: 'hydrate'; progress: Progress }
  | { type: 'character'; index: number | null }
  | { type: 'evidence'; evidence: Evidence }
  | { type: 'toggleTask'; careerId: string; taskId: string }
  | { type: 'journalAdd'; entry: JournalEntry }
  | { type: 'journalRemove'; id: string }
  | { type: 'planCareer'; careerId: string }
  | { type: 'explored'; careerId: string }
  | { type: 'dnaAnswer'; id: string; option: string }
  | { type: 'dnaSet'; patch: Partial<Progress['dna']> }
  | { type: 'dnaBack' }
  | { type: 'dnaReset' }
  | { type: 'interestAnswer'; id: string; rating: number }
  | { type: 'country'; country: Progress['country'] }
  | { type: 'statedInterests'; text: string }
  | { type: 'skillsAndProjects'; text: string }
  | { type: 'reset' };

function reducer(state: Progress, action: Action): Progress {
  switch (action.type) {
    case 'hydrate': return action.progress;
    case 'character': return { ...state, character: action.index };
    case 'evidence': return { ...state, evidence: [...state.evidence, action.evidence] };
    case 'toggleTask': {
      const current = state.tasks[action.careerId] ?? [];
      const next = current.includes(action.taskId) ? current.filter(id => id !== action.taskId) : [...current, action.taskId];
      return { ...state, tasks: { ...state.tasks, [action.careerId]: next } };
    }
    case 'journalAdd': return { ...state, journal: [action.entry, ...state.journal] };
    case 'journalRemove': return { ...state, journal: state.journal.filter(e => e.id !== action.id) };
    case 'planCareer': return { ...state, planCareer: action.careerId };
    case 'explored': return state.explored.includes(action.careerId) ? state : { ...state, explored: [...state.explored, action.careerId] };
    case 'dnaAnswer': return { ...state, dna: { ...state.dna, answers: { ...state.dna.answers, [action.id]: action.option } } };
    case 'dnaSet': return { ...state, dna: { ...state.dna, ...action.patch } };
    case 'dnaBack': { const a = { ...state.dna.answers }; delete a[Object.keys(a).pop() ?? '']; return { ...state, dna: { answers: a, tie: null, recon: null } }; }
    case 'dnaReset': return { ...state, dna: emptyProgress().dna };
    case 'interestAnswer': return { ...state, interests: { ...state.interests, [action.id]: action.rating } };
    case 'country': return { ...state, country: action.country };
    case 'statedInterests': return { ...state, statedInterests: action.text };
    case 'skillsAndProjects': return { ...state, skillsAndProjects: action.text };
    case 'reset': return emptyProgress();
  }
}

type ProgressContextValue = {
  progress: Progress;
  dispatch: Dispatch<Action>;
  loaded: boolean;
  traits: Record<Trait, number>;
  /** True once the Learning DNA profiler has been completed. */
  profiled: boolean;
  hasSignal: boolean;
  ranked: Ranked[];
  xp: number;
  level: ReturnType<typeof levelInfo>;
  badges: Badge[];
};

const ProgressContext = createContext<ProgressContextValue | null>(null);

export function ProgressProvider({ userId, children }: { userId: string; children: ReactNode }) {
  const [progress, dispatch] = useReducer(reducer, undefined, emptyProgress);
  const [loaded, setLoaded] = useState(false);
  const saveQueue = useMemo(createSaveQueue, [userId]);
  const latestProgress = useRef(progress);
  latestProgress.current = progress;

  useEffect(() => {
    let alive = true;
    setLoaded(false);
    loadProgress(userId).then(p => { if (alive) { dispatch({ type: 'hydrate', progress: p }); setLoaded(true); } }).catch(() => { /* stay unloaded so nothing is overwritten */ });
    return () => { alive = false; };
  }, [userId]);

  useEffect(() => {
    if (!loaded) return;
    const snapshot = progress;
    const t = setTimeout(() => {
      void saveQueue(() => saveProgress(userId, snapshot), () => latestProgress.current === snapshot)
        .catch(error => console.error('Could not save progress', error));
    }, userId === 'guest' ? 0 : 800); // debounce server saves
    return () => clearTimeout(t);
  }, [progress, loaded, userId, saveQueue]);

  const value = useMemo<ProgressContextValue>(() => {
    const traits = traitValues(progress.character);
    const xp = computeXp(progress);
    return {
      progress, dispatch, loaded, traits,
      profiled: stageOf(progress.dna).kind === 'done',
      hasSignal: progress.character !== null || Object.keys(progress.dna.answers).length > 0,
      ranked: rankCareers(traits, progress.evidence),
      xp, level: levelInfo(xp), badges: computeBadges(progress),
    };
  }, [progress, loaded]);

  return <ProgressContext.Provider value={value}>{children}</ProgressContext.Provider>;
}

export function useProgress() {
  const ctx = useContext(ProgressContext);
  if (!ctx) throw new Error('useProgress must be used inside <ProgressProvider>');
  return ctx;
}
