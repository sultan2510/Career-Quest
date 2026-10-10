import type { Decision, Evidence, LoggedDecision, Progress, SimulationDraft } from '@/lib/types';

export function sceneId(careerId: string, scene: number): string {
  return `${careerId}:${scene}`;
}

export function recordSimulationDecision(
  progress: Progress,
  careerId: string,
  decision: Decision,
  runId: string,
  timestamp: string,
): Progress {
  const existing = progress.simulationDrafts[careerId];
  const draft: SimulationDraft = existing ?? {
    run_id: runId,
    career_id: careerId,
    current_scene_id: sceneId(careerId, decision.scene),
    decision_log: [],
    started_at: timestamp,
  };
  const logged: LoggedDecision = {
    scene_id: sceneId(careerId, decision.scene),
    user_choice: decision.text,
    ...(decision.source === 'free-text' ? { free_text_explanation: decision.text } : {}),
    timestamp,
    outcome: decision.outcome,
    quality: decision.quality,
    source: decision.source,
  };
  // Replacing a choice also discards later scenes based on the previous choice.
  const decision_log = [
    ...draft.decision_log.filter(entry => Number(entry.scene_id.split(':').at(-1)) < decision.scene),
    logged,
  ];
  return {
    ...progress,
    simulationDrafts: {
      ...progress.simulationDrafts,
      [careerId]: { ...draft, current_scene_id: logged.scene_id, decision_log },
    },
  };
}

export function advanceSimulation(progress: Progress, careerId: string, nextSceneId: string): Progress {
  const draft = progress.simulationDrafts[careerId];
  if (!draft) return progress;
  return {
    ...progress,
    simulationDrafts: {
      ...progress.simulationDrafts,
      [careerId]: { ...draft, current_scene_id: nextSceneId },
    },
  };
}

export function finishSimulation(progress: Progress, careerId: string, enjoyment: number, confidence: number, timestamp: string): Progress {
  const draft = progress.simulationDrafts[careerId];
  if (!draft || draft.decision_log.length < 2) throw new Error('Complete both scenes before saving your reflection.');
  const decisions: Decision[] = draft.decision_log.map(entry => ({
    scene: Number(entry.scene_id.split(':').at(-1)),
    text: entry.user_choice,
    outcome: entry.outcome,
    quality: entry.quality,
    source: entry.source,
  }));
  const decision_log = draft.decision_log.map((entry, index) => index === draft.decision_log.length - 1
    ? { ...entry, enjoyment_rating: enjoyment, confidence_rating: confidence }
    : entry);
  const evidence: Evidence = { id: draft.run_id, careerId, enjoyment, confidence, decisions, decision_log, at: timestamp };
  const simulationDrafts = { ...progress.simulationDrafts };
  delete simulationDrafts[careerId];
  return {
    ...progress,
    simulationDrafts,
    evidence: [...progress.evidence.filter(item => item.id !== evidence.id), evidence],
    explored: progress.explored.includes(careerId) ? progress.explored : [...progress.explored, careerId],
  };
}

export function resumeSimulation(draft: SimulationDraft | undefined): { scene: number; result: Decision | null } {
  if (!draft) return { scene: 0, result: null };
  if (draft.current_scene_id === 'reflection') return { scene: 2, result: null };
  const parsed = Number(draft.current_scene_id.split(':').at(-1));
  const scene = parsed === 1 ? 1 : 0;
  const entry = draft.decision_log.find(item => item.scene_id === sceneId(draft.career_id, scene));
  return {
    scene,
    result: entry ? {
      scene, text: entry.user_choice, outcome: entry.outcome,
      quality: entry.quality, source: entry.source,
    } : null,
  };
}
