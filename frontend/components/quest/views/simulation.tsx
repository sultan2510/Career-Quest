'use client';
import { useState } from 'react';
import { ArrowRight, ChevronRight, FlaskConical, Lightbulb, TrendingUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useProgress } from '@/components/providers/progress-provider';
import { CareerIcon, SenseiPanel, useNav } from '@/components/quest/common';
import { careerById } from '@/lib/data/careers';
import type { Decision } from '@/lib/types';
import { resumeSimulation, sceneId } from '@/lib/simulation-progress';

const FREE_TEXT_OUTCOME = 'Your own approach opens a conversation. In real work you’d explain your reasoning, test it against evidence, and adjust as you learn more.';

export function SimulationView() {
  const { simCareer, startSim, go } = useNav();
  const { ranked, hasSignal, progress } = useProgress();
  const career = simCareer ? careerById(simCareer) : undefined;
  if (!career) return <>
    <div className="section-heading"><div><h2>Choose a day to try</h2><p>Two short scenes. Make a call, then notice how it felt.</p></div></div>
    <div className="career-grid">{ranked.map(r => <article className="career-card" key={r.career.id}>
      <div className="career-top"><CareerIcon career={r.career} /><span className={hasSignal ? 'fit-badge' : 'fit-badge muted'}>{hasSignal ? `${r.score.overall}% fit` : 'Not matched yet'}</span></div>
      <h3>{r.career.name}</h3><p className="career-desc">{r.career.category}</p>
      <div className="career-bottom"><span>{progress.simulationDrafts[r.career.id] ? 'Run in progress' : '2 scenes · 3 minutes'}</span><Button variant="link" className="text-action" onClick={() => startSim(r.career.id)}>{progress.simulationDrafts[r.career.id] ? 'Resume the day' : 'Start the day'} <ArrowRight /></Button></div>
    </article>)}</div>
  </>;
  return <Run key={career.id} careerId={career.id} onSwitch={() => { startSim(null); go('simulation'); }} />;
}

function Run({ careerId, onSwitch }: { careerId: string; onSwitch: () => void }) {
  const career = careerById(careerId)!;
  const { progress, recordDecision, advanceRun, completeRun, retrySave } = useProgress();
  const { go } = useNav();
  const [initial] = useState(() => resumeSimulation(progress.simulationDrafts[careerId]));
  const [scene, setScene] = useState(initial.scene);
  const [result, setResult] = useState<Decision | null>(initial.result);
  const [custom, setCustom] = useState('');
  const [enjoyment, setEnjoyment] = useState(3);
  const [confidence, setConfidence] = useState(3);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const current = career.scenes[scene as 0 | 1];
  const choose = async (decision: Decision) => {
    if (busy) return;
    setBusy(true); setError('');
    try {
      await recordDecision(careerId, decision);
      setResult(decision);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Your decision could not be saved. Please try again.');
    } finally { setBusy(false); }
  };
  const next = async () => {
    if (!result || busy) return;
    setBusy(true); setError('');
    try {
      await advanceRun(careerId, scene === 0 ? sceneId(careerId, 1) : 'reflection');
      setResult(null); setCustom(''); setScene(scene + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Your progress could not be saved. Please try again.');
    } finally { setBusy(false); }
  };
  const save = async () => {
    if (busy) return;
    setBusy(true); setError('');
    try {
      if (progress.simulationDrafts[careerId]) await completeRun(careerId, enjoyment, confidence);
      else await retrySave();
      go('reflection');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Your reflection could not be saved. Please try again.');
    } finally { setBusy(false); }
  };

  return <div className="content-grid">
    <section className="workspace">
      <div className="eyebrow"><FlaskConical size={14} />Day in the life · {career.name}</div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {busy && <p role="status" className="text-sm">Saving your decision…</p>}
      <div className="quest-progress"><div className="progress-track"><div className="progress-fill" style={{ width: `${scene >= 2 ? 100 : (scene + (result ? 1 : 0.4)) / 3 * 100}%` }} /></div><span>{scene >= 2 ? 'Time to reflect' : `Scene ${scene + 1} of 2`}</span></div>
      {current ? <>
        <span className="small-tag">{current.time}</span>
        <h2>{current.title}</h2><p>{current.prompt}</p>
        {!result ? <>
          <div className="answer-options">{current.choices.map((c, i) => <Button key={c.text} variant="outline" className="answer" disabled={busy} onClick={() => void choose({ scene, text: c.text, outcome: c.outcome, quality: c.quality, source: 'choice' })}><span className="answer-number">{String.fromCharCode(65 + i)}</span>{c.text}<ChevronRight className="ml-auto" /></Button>)}</div>
          <label htmlFor="own" className="block text-sm font-semibold mb-2">Or take your own approach</label>
          <textarea id="own" className="custom-answer" placeholder="What would you do, and why?" maxLength={600} value={custom} onChange={e => setCustom(e.target.value)} />
          <Button variant="outline" className="mt-3" disabled={!custom.trim() || busy} onClick={() => void choose({ scene, text: custom.trim(), outcome: FREE_TEXT_OUTCOME, quality: null, source: 'free-text' })}>Try my approach <ArrowRight /></Button>
        </> : <div aria-live="polite">
          <div className="consequence"><strong className="text-sm">Your decision</strong><p>{result.text}</p></div>
          <h3 className="font-bold">What happens next?</h3><p>{result.outcome}</p>
          <span className="small-tag">{result.source === 'choice' ? 'Scripted scenario outcome' : 'Your own approach · Not scored in this version'}</span>
          <div className="flex gap-3 mt-6 flex-wrap"><Button disabled={busy} onClick={() => void next()}>{scene === 0 ? 'Continue the day' : 'Reflect on your experience'} <ArrowRight /></Button><Button variant="outline" disabled={busy} onClick={() => setResult(null)}>Try another choice</Button></div>
        </div>}
      </> : <>
        <h2>How did that day feel?</h2>
        <p>There’s a difference between being good at something and enjoying it. Both matter.</p>
        <div className="rating-grid">
          <div><label htmlFor="enjoyment">Enjoyment · {enjoyment}/5</label><input id="enjoyment" type="range" min={1} max={5} value={enjoyment} onChange={e => setEnjoyment(Number(e.target.value))} /><div className="rating-endpoints"><span>Draining</span><span>Energizing</span></div></div>
          <div><label htmlFor="confidence">Confidence · {confidence}/5</label><input id="confidence" type="range" min={1} max={5} value={confidence} onChange={e => setConfidence(Number(e.target.value))} /><div className="rating-endpoints"><span>Unsure</span><span>Confident</span></div></div>
        </div>
        <div className="sensei-tip"><Lightbulb /><span>Your ratings update this career’s fit. A lower score is a useful discovery, not a failure.</span></div>
        <div className="flex gap-3 mt-6 flex-wrap"><Button disabled={busy} onClick={() => void save()}>See how your path evolved <TrendingUp /></Button><Button variant="outline" disabled={busy} onClick={onSwitch}>Pick a different career</Button></div>
      </>}
    </section>
    <SenseiPanel />
  </div>;
}
