'use client';
import { useState } from 'react';
import { ArrowRight, ChartNoAxesCombined, Lightbulb } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useProgress } from '@/components/providers/progress-provider';
import { CareerCard, useNav } from '@/components/quest/common';
import { surpriseCareer } from '@/lib/scoring';

const DIMENSIONS = [['love', 'Exploratory preference'], ['goodAt', 'Simulation confidence']] as const;

export function CareersView() {
  const { ranked, traits, hasSignal, progress } = useProgress();
  const { startSim } = useNav();
  const [compare, setCompare] = useState(false);
  const [picked, setPicked] = useState<string[]>([]);
  const surprise = surpriseCareer(ranked, traits);
  const toggle = (id: string, on: boolean) => setPicked(p => on ? (p.length < 3 ? [...p, id] : p) : p.filter(x => x !== id));
  const shown = ranked.filter(r => picked.includes(r.career.id));

  return <>
    <div className="section-heading">
      <div><h2>Your career possibilities</h2><p>Prototype matches · {progress.evidence.length ? 'Includes your simulation feedback' : 'A starting point, not a prediction'}</p></div>
      <Button variant={compare ? 'default' : 'outline'} onClick={() => setCompare(!compare)}><ChartNoAxesCombined />{compare ? 'Done comparing' : 'Compare paths'}</Button>
    </div>
    {compare && <p className="text-sm mb-3" style={{ color: 'var(--muted-foreground)' }}>Tick up to three careers to compare them side by side.</p>}
    <div className="career-grid">{ranked.map(r => <CareerCard key={r.career.id} career={r.career} score={hasSignal ? r.score.overall : null} label={r.delta ? `${r.delta > 0 ? '+' : ''}${r.delta} from simulations` : 'A possible path'} picked={picked.includes(r.career.id)} onPick={compare ? on => toggle(r.career.id, on) : undefined} />)}</div>
    {compare && shown.length > 0 && <section className="workspace mt">
      <h2>Explore your early signals</h2>
      <div className="career-grid">{shown.map(r => <div key={r.career.id}><h3 className="font-bold mb-5">{r.career.name}</h3>{DIMENSIONS.map(([key, label]) => <div key={key} className="mb-4"><div className="flex justify-between text-xs mb-2"><span>{label}</span><span>{r.score[key]}%</span></div><div className="progress-track"><div className="progress-fill" style={{ width: `${r.score[key]}%` }} /></div></div>)}</div>)}</div>
      <p className="text-xs">These exploratory signals use character traits and simulation feedback. Open the Ikigai map for sourced occupation and labour-market evidence.</p>
    </section>}
    <section className="workspace mt">
      <div className="eyebrow"><Lightbulb size={14} />A little outside your comfort zone</div>
      <h2>{surprise.career.name}: your surprise path</h2>
      <p>{surprise.career.description} Sometimes the most interesting discovery is the one you didn’t expect.</p>
      <Button variant="outline" onClick={() => startSim(surprise.career.id)}>Try this unexpected path <ArrowRight /></Button>
    </section>
  </>;
}
