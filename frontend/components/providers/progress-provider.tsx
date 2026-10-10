'use client';
import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState, type Dispatch, type ReactNode } from 'react';
import { loadProgress, saveProgress } from '@/lib/storage';
import { createSaveQueue } from '@/lib/save-queue';
import { stageOf } from '@/lib/dna';
import { computeBadges, computeXp, levelInfo, rankCareers, traitValues, type Badge, type Ranked } from '@/lib/scoring';
import { emptyProgress, type Evidence, type JournalEntry, type MentorMessage, type Progress, type Trait } from '@/lib/types';
import { advanceSimulation, finishSimulation, recordSimulationDecision } from '@/lib/simulation-progress';
import type { Decision } from '@/lib/types';

type Action =
  | { type: 'hydrate'; progress: Progress }
  | { type: 'character'; index: number | null }
  | { type: 'evidence'; evidence: Evidence }
  | { type: 'toggleTask'; careerId: string; taskId: string }
  | { type: 'journalAdd'; entry: JournalEntry }
  | { type: 'journalRemove'; id: string }
  | { type: 'mentorMessage'; message: MentorMessage }
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
  | { type: 'simulationDecision'; careerId: string; decision: Decision; runId: string; timestamp: string }
  | { type: 'simulationAdvance'; careerId: string; sceneId: string }
  | { type: 'simulationFinish'; careerId: string; enjoyment: number; confidence: number; timestamp: string }
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
    case 'mentorMessage': return { ...state, mentorMessages: [...state.mentorMessages, action.message].slice(-30) };
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
    case 'simulationDecision': return recordSimulationDecision(state, action.careerId, action.decision, action.runId, action.timestamp);
    case 'simulationAdvance': return advanceSimulation(state, action.careerId, action.sceneId);
    case 'simulationFinish': return finishSimulation(state, action.careerId, action.enjoyment, action.confidence, action.timestamp);
    case 'reset': return emptyProgress();
  }
}

type ProgressContextValue = {
  progress: Progress;
  dispatch: Dispatch<Action>;
  loaded: boolean;
  loadError: string | null;
  retryLoad: () => void;
  saveStatus: 'saved' | 'saving' | 'error';
  retrySave: () => Promise<void>;
  resetProgress: () => Promise<void>;
  recordDecision: (careerId: string, decision: Decision) => Promise<void>;
  advanceRun: (careerId: string, sceneId: string) => Promise<void>;
  completeRun: (careerId: string, enjoyment: number, confidence: number) => Promise<void>;
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
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | 'error'>('saved');
  const saveQueue = useMemo(createSaveQueue, [userId]);
  const latestProgress = useRef(progress);
  const lastSaved = useRef<Progress | null>(null);
  const directSave = useRef<Progress | null>(null);
  latestProgress.current = progress;

  useEffect(() => {
    let alive = true;
    setLoaded(false);
    setLoadError(null);
    loadProgress(userId).then(p => { if (alive) { lastSaved.current = p; latestProgress.current = p; dispatch({ type: 'hydrate', progress: p }); setLoaded(true); } })
      .catch(error => { if (alive) setLoadError(error instanceof Error ? error.message : 'Could not load your progress.'); });
    return () => { alive = false; };
  }, [userId, loadAttempt]);

  const saveSnapshot = useCallback((snapshot: Progress) => {
    if (latestProgress.current === snapshot) setSaveStatus('saving');
    return saveQueue(() => saveProgress(userId, snapshot), () => latestProgress.current === snapshot)
      .then(() => {
        if (latestProgress.current === snapshot) {
          lastSaved.current = snapshot;
          setSaveStatus('saved');
        }
      })
      .catch(error => {
        if (latestProgress.current === snapshot) setSaveStatus('error');
        throw error;
      });
  }, [saveQueue, userId]);

  const retrySave = useCallback(() => saveSnapshot(latestProgress.current), [saveSnapshot]);

  const persist = useCallback(async (action: Action) => {
    const next = reducer(latestProgress.current, action);
    directSave.current = next;
    latestProgress.current = next;
    dispatch({ type: 'hydrate', progress: next });
    try {
      await saveSnapshot(next);
    } finally {
      if (directSave.current === next) directSave.current = null;
    }
  }, [saveSnapshot]);

  const recordDecision = useCallback((careerId: string, decision: Decision) => {
    return persist({ type: 'simulationDecision', careerId, decision, runId: crypto.randomUUID(), timestamp: new Date().toISOString() });
  }, [persist]);
  const advanceRun = useCallback((careerId: string, sceneId: string) => persist({ type: 'simulationAdvance', careerId, sceneId }), [persist]);
  const completeRun = useCallback((careerId: string, enjoyment: number, confidence: number) => {
    return persist({ type: 'simulationFinish', careerId, enjoyment, confidence, timestamp: new Date().toISOString() });
  }, [persist]);
  const resetProgress = useCallback(() => persist({ type: 'reset' }), [persist]);

  useEffect(() => {
    if (!loaded || progress === lastSaved.current || progress === directSave.current) return;
    setSaveStatus('saving');
    const snapshot = progress;
    const t = setTimeout(() => {
      void saveSnapshot(snapshot)
        .catch(error => console.error('Could not save progress', error));
    }, 800); // debounce account and guest database saves
    return () => clearTimeout(t);
  }, [progress, loaded, userId, saveSnapshot]);

  const value = useMemo<ProgressContextValue>(() => {
    const traits = traitValues(progress.character);
    const xp = computeXp(progress);
    return {
      progress, dispatch, loaded, loadError, retryLoad: () => setLoadAttempt(n => n + 1),
      saveStatus, retrySave, resetProgress, recordDecision, advanceRun, completeRun, traits,
      profiled: stageOf(progress.dna).kind === 'done',
      hasSignal: progress.character !== null || Object.keys(progress.dna.answers).length > 0,
      ranked: rankCareers(traits, progress.evidence),
      xp, level: levelInfo(xp), badges: computeBadges(progress),
    };
  }, [progress, loaded, loadError, saveStatus, retrySave, resetProgress, recordDecision, advanceRun, completeRun]);

  return <ProgressContext.Provider value={value}>{children}</ProgressContext.Provider>;
}

export function useProgress() {
  const ctx = useContext(ProgressContext);
  if (!ctx) throw new Error('useProgress must be used inside <ProgressProvider>');
  return ctx;
}
