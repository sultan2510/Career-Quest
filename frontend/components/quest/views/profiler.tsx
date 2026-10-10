'use client';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ArrowLeft, ArrowRight, BookOpen, Brain, Check, Compass, LayoutGrid, Lightbulb, PenLine, RotateCcw, Shapes, Sprout, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useProgress } from '@/components/providers/progress-provider';
import { useNav } from '@/components/quest/common';
import { References } from '@/components/quest/references';
import { DNA_PARTS } from '@/lib/data/dna';
import type { DnaScenario } from '@/lib/dna-types';
import { PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer } from 'recharts';
import { BRANCH_DIM, DIMS, RECON, RIASEC_NAMES, ambiguity, careerFit, depth, profile, riasecProfile, stageOf } from '@/lib/dna';

// One icon per part, matching what that part is actually about.
const PART_ICONS = [Compass, LayoutGrid, Users, BookOpen, Lightbulb, PenLine, Shapes];
const PART_TONES = ['qt-1', 'qt-2', 'qt-3', 'qt-4'];
const partTone = (n: number) => PART_TONES[(n - 1) % PART_TONES.length];
const partIcon = (n: number) => PART_ICONS[(n - 1) % PART_ICONS.length];

const reduced = () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Choice cards. Shows the pick before the next question replaces it. */
function Options({ options, onPick }: { options: { id: string; text: string }[]; onPick: (id: string) => void }) {
  const [chosen, setChosen] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  const pick = (id: string) => {
    if (chosen) return;
    setChosen(id);
    timer.current = setTimeout(() => onPick(id), reduced() ? 0 : 420);
  };
  return <div className="q-options" role="group" aria-label="Choose what you would do">
    {options.map((o, i) => (
      <button type="button" key={o.id} disabled={!!chosen} onClick={() => pick(o.id)}
        className={`q-option${chosen === o.id ? ' chosen' : ''}${chosen && chosen !== o.id ? ' dim' : ''}`}
        style={{ animationDelay: `${i * 55}ms` }}>
        <span className="q-mark" aria-hidden="true"><Check /></span>
        <span>{o.text}</span>
      </button>
    ))}
  </div>;
}

/** Split each narrative paragraph into sentences — most scenarios store the whole scene as one paragraph. */
const beat = (narrative: string[]) => narrative.map(t =>
  (t.match(/[^.!?]+[.!?]+["')\]]*\s*|[^.!?]+$/g) ?? [t]).map(x => x.trim()).filter(Boolean));

/** The scene: sentences arrive one at a time, then the decision appears. */
function Scene({ s, instant, onPick, back }: { s: DnaScenario; instant: boolean; onPick: (id: string) => void; back: ReactNode }) {
  const paras = useMemo(() => beat(s.narrative), [s.narrative]);
  const total = paras.reduce((n, p) => n + p.length, 0);
  const [shown, setShown] = useState(() => (instant || reduced() ? total : 1));
  const done = shown >= total;
  useEffect(() => {
    if (done) return;
    const t = setTimeout(() => setShown(n => n + 1), 620);
    return () => clearTimeout(t);
  }, [shown, done]);
  let seen = 0;
  return <>
    <div className="q-narrative">
      {paras.map((sentences, pi) => {
        const from = seen; seen += sentences.length;
        const count = Math.max(0, Math.min(sentences.length, shown - from));
        if (count === 0) return null;
        return <p key={pi}>{sentences.slice(0, count).map((t, si) => <span className="q-line" key={si}>{t} </span>)}</p>;
      })}
    </div>
    {!done && <button type="button" className="q-skip" onClick={() => setShown(total)}>Skip the scene</button>}
    {done && <>
      <h2 className="q-prompt">{s.prompt}</h2>
      <Options options={s.options} onPick={onPick} />
      <details className="q-why"><summary>Why we ask this</summary>
        <p>{s.rationale}</p>
        {s.refs.length > 0 && <p>Sources: {s.refs.map(n => <a key={n} href={`#ref-${n}`} style={{ textDecoration: 'underline', marginRight: 8 }}>[{n}]</a>)}</p>}
      </details>
      <div className="q-foot">{back}</div>
    </>}
  </>;
}

/** The divider between the seven parts. */
function Chapter({ n, onDone }: { n: number; onDone: () => void }) {
  const part = DNA_PARTS.find(p => p.n === n)!, Icon = partIcon(n);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onDone(); } };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onDone]);
  return <section className="q-chapter">
    <div className="quest-dots" role="img" aria-label={`Part ${n} of ${DNA_PARTS.length}`}>
      {DNA_PARTS.map(p => <i key={p.n} className={p.n === n ? 'now' : p.n < n ? 'done' : ''} />)}
    </div>
    <span className="q-chapter-icon"><Icon /></span>
    <p className="q-chapter-eyebrow">Part {n} of {DNA_PARTS.length}</p>
    <h1>{part.title}</h1>
    <p className="q-chapter-sub">{part.subtitle}</p>
    {part.intro && <p className="q-chapter-intro">{part.intro}</p>}
    <Button className="mt-2" onClick={onDone}>Continue <ArrowRight /></Button>
  </section>;
}

// The Holland hexagon orders the six types so that neighbours are the most alike; the radar keeps that
// order rather than sorting by score, so the shape's geometry stays comparable between people.
const HOLLAND = ['R', 'I', 'A', 'S', 'E', 'C'];

type TickProps = { x?: number; y?: number; textAnchor?: 'start' | 'middle' | 'end' | 'inherit'; payload?: { value?: string } };
const AngleTick = ({ x = 0, y = 0, textAnchor = 'middle', payload }: TickProps) => (
  <g>
    <text x={x} y={y} textAnchor={textAnchor} dy={-3} style={{ fill: 'var(--part)', fontSize: 15, fontWeight: 800 }}>{payload?.value}</text>
    <text x={x} y={y} textAnchor={textAnchor} dy={14} style={{ fill: 'var(--muted-foreground)', fontSize: 11.5 }}>{RIASEC_NAMES[payload?.value ?? ''] ?? ''}</text>
  </g>
);

function RiasecCard({ rc }: { rc: ReturnType<typeof riasecProfile> }) {
  const ref = useRef<HTMLDivElement>(null);
  // Recharts writes these as SVG attributes, where var() does not resolve — so read the resolved colour.
  const [part, setPart] = useState('#277E75');
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const v = getComputedStyle(el).getPropertyValue('--part').trim();
    if (v) setPart(v);
  }, []);
  const byLetter = Object.fromEntries(rc.ranked.map(r => [r.letter, r]));
  const data = HOLLAND.map(letter => ({ type: letter, value: Math.round((byLetter[letter]?.norm ?? 0) * 100) }));
  return <div className="q-riasec" ref={ref}>
    <div className="q-riasec-side">
      <div className="q-riasec-code">{rc.code}</div>
      <p className="q-riasec-expand">{rc.ranked.slice(0, 3).map(r => r.name).join(' · ')}</p>
      <ul className="q-riasec-legend">
        {rc.ranked.map((r, i) => <li key={r.letter} className={i < 3 ? 'on' : 'off'}>
          <span className="q-riasec-letter">{r.letter}</span>
          <span className="q-riasec-name">{r.name}</span>
          <span className="q-riasec-val">{Math.round(r.norm * 100)}%</span>
        </li>)}
      </ul>
    </div>
    <div className="q-riasec-radar">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="66%" margin={{ top: 34, right: 46, bottom: 34, left: 46 }}>
          <defs>
            <radialGradient id="riasecFill" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor={part} stopOpacity={0.45} />
              <stop offset="100%" stopColor={part} stopOpacity={0.1} />
            </radialGradient>
          </defs>
          <PolarGrid stroke={part} strokeOpacity={0.22} strokeDasharray="2 5" />
          <PolarAngleAxis dataKey="type" tick={<AngleTick />} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} tickLine={false} />
          <Radar dataKey="value" stroke={part} strokeWidth={2} fill="url(#riasecFill)" fillOpacity={1}
            dot={{ r: 3.5, fill: part, strokeWidth: 0 }} isAnimationActive animationDuration={900} animationEasing="ease-out" />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  </div>;
}

export function ProfilerView() {  const { progress, dispatch } = useProgress();
  const { go } = useNav();
  const [begun, setBegun] = useState(false);
  const st = progress.dna;
  const started = Object.keys(st.answers).length > 0;
  const stage = stageOf(st);
  const activePart = stage.kind === 'scenario' ? stage.s.part : null;
  const sid = stage.kind === 'scenario' ? stage.s.id : null;
  const [chapter, setChapter] = useState<number | null>(null);
  // Scenes already answered through, so stepping Back doesn't replay the reveal.
  const revealed = useRef<Set<string>>(new Set());

  // A part we haven't opened yet gets its chapter card first.
  const opened = useRef<Set<number>>(new Set());
  useEffect(() => {
    if (activePart === null || opened.current.has(activePart)) return;
    opened.current.add(activePart);
    setChapter(activePart);
  }, [activePart]);

  // The card holds for a beat, then yields to the question. Enter or Space skips it.
  useEffect(() => {
    if (chapter === null) return;
    const t = setTimeout(() => setChapter(null), reduced() ? 1100 : 2800);
    return () => clearTimeout(t);
  }, [chapter]);

  // Each scene opens at the top, like turning a page.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.scrollTo({ top: 0, behavior: reduced() ? 'auto' : 'smooth' });
  }, [chapter, sid]);

  const parts = Object.keys(st.answers).map(k => parseInt(k, 10));
  const furthest = parts.length ? Math.max(...parts) : 0;
  const current = activePart ?? furthest;

  const frame = (body: ReactNode, tone: string) => (
    <div className={`quest-frame ${tone}`}>
      <div className="quest-bg" aria-hidden="true" />
      <header className="quest-bar">
        <div className="logo"><div className="logo-mark"><Sprout size={20} /></div><div>Career<span className="accent">Quest</span></div></div>
        <div className="quest-dots" role="img" aria-label={current ? `Part ${current} of ${DNA_PARTS.length}` : 'Not started'}>
          {DNA_PARTS.map(p => <i key={p.n} className={p.n === current ? 'now' : p.n < current ? 'done' : ''} />)}
        </div>
        <Button variant="ghost" size="sm" onClick={() => go('journey')}>Exit</Button>
      </header>
      <div className="quest-body">
        <nav className="quest-rail" aria-label="Parts">
          {DNA_PARTS.map(p => (
            <div key={p.n} className={`rail-step${p.n === current ? ' now' : p.n < current ? ' done' : ''}`}
              aria-current={p.n === current ? 'step' : undefined}>
              <span className="rail-node">{p.n < current ? <Check /> : p.n}</span>
              <span className="rail-label">{p.title}</span>
            </div>
          ))}
        </nav>
        <div className="quest-stage"><div className="quest-panel">{body}</div></div>
      </div>
    </div>
  );

  if (!started && !begun) return frame(
    <section className="q-intro">
      <span className="q-chip"><Brain />The Learning DNA Profiler</span>
      <h1>Seven short stories. No right answers.</h1>
      <p>About 10 to 15 decisions, in seven parts. Each choice shows how you think, and later questions adapt to your earlier answers. Nothing here is timed and nothing is a test.</p>
      <Button onClick={() => setBegun(true)}>Begin <ArrowRight /></Button>
    </section>, 'qt-1');

  if (chapter !== null) return frame(<Chapter n={chapter} onDone={() => setChapter(null)} />, partTone(chapter));

  if (stage.kind === 'scenario') {
    const s = stage.s, part = DNA_PARTS.find(p => p.n === s.part)!, Icon = partIcon(part.n);
    const back = started ? <Button variant="ghost" size="sm" onClick={() => dispatch({ type: 'dnaBack' })}><ArrowLeft />Back</Button> : null;
    return frame(
      <section className="q-enter" key={s.id}>
        <span className="q-chip"><Icon />Part {part.n} of {DNA_PARTS.length} · {part.title}{s.parent ? ' · Follow-up' : ''}</span>
        <h1 className="q-scene-title">{s.title}</h1>
        <Scene s={s} instant={revealed.current.has(s.id)} back={back}
          onPick={id => { revealed.current.add(s.id); dispatch({ type: 'dnaAnswer', id: s.id, option: id }); }} />
      </section>, partTone(part.n));
  }

  if (stage.kind === 'recon') return frame(
    <section className="q-enter">
      <span className="q-chip">Quick check</span>
      <h1 className="q-scene-title">Some of your answers pull in different directions</h1>
      <div className="q-narrative"><p>You notice that in group settings you read people well, but when making personal decisions you prefer to work alone. Which statement resonates more?</p></div>
      <div className="q-options" role="group" aria-label="Choose the statement that resonates more">
        {RECON.map((r, i) => <button type="button" key={i} className="q-option" style={{ animationDelay: `${i * 55}ms` }} onClick={() => dispatch({ type: 'dnaSet', patch: { recon: i } })}><span className="q-mark" aria-hidden="true"><Check /></span><span>{r.text}</span></button>)}
      </div>
      <div className="q-foot"><Button variant="ghost" size="sm" onClick={() => dispatch({ type: 'dnaBack' })}><ArrowLeft />Back</Button></div>
    </section>, 'qt-1');

  if (stage.kind === 'tie') return frame(
    <section className="q-enter">
      <span className="q-chip">Tie-breaker</span>
      <h1 className="q-scene-title">Two strengths are almost level</h1>
      <div className="q-narrative"><p>Your answers rate <strong>{DIMS[stage.a].label}</strong> and <strong>{DIMS[stage.b].label}</strong> about equally. Which sounds more like you?</p></div>
      <div className="q-options" role="group" aria-label="Choose which sounds more like you">
        {[stage.a, stage.b].map((k, i) => <button type="button" key={k} className="q-option" style={{ animationDelay: `${i * 55}ms` }} onClick={() => dispatch({ type: 'dnaSet', patch: { tie: k } })}><span className="q-mark" aria-hidden="true"><Check /></span><span>{DIMS[k].blurb}</span></button>)}
      </div>
      <div className="q-foot"><Button variant="ghost" size="sm" onClick={() => dispatch({ type: 'dnaBack' })}><ArrowLeft />Back</Button></div>
    </section>, 'qt-1');

  const p = profile(st), fit = careerFit(st), d = depth(st), amb = ambiguity(st), rc = riasecProfile(st);
  return frame(
    <section className="q-enter">
      <span className="q-chip">Your results</span>
      <h1 className="q-scene-title">Your Learning DNA</h1>
      <div className="q-narrative"><p>Each bar is your score out of the points available from the questions you answered. Order reflects career weighting. This is a starting point, not a verdict.</p></div>
      <div style={{ display: 'grid', gap: 10, margin: '0 0 26px' }}>{p.map(r => <div key={r.key}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}><span>{DIMS[r.key].label}</span><span>{r.asked ? `${Math.round(r.norm * 100)}% · ${r.asked} question${r.asked > 1 ? 's' : ''}` : 'not assessed'}{d.byDim[r.key] ? ` · depth ${d.byDim[r.key]! + 1}` : ''}</span></div>
        <div style={{ height: 8, borderRadius: 4, background: 'var(--border)' }}><div style={{ width: `${r.norm * 100}%`, height: '100%', borderRadius: 4, background: 'currentColor', opacity: 0.75 }} /></div>
      </div>)}</div>
      <h2 className="q-prompt">Closest career families</h2>
      <ol style={{ paddingLeft: 20, margin: '0 0 22px' }}>{fit.slice(0, 3).map(f => <li key={f.name}><strong>{f.name}</strong> · {f.riasec} · {Math.round(f.fit * 100)}% match</li>)}</ol>
      {rc.assessed && <>
        <h2 className="q-prompt">Your RIASEC alignment</h2>
        <RiasecCard rc={rc} />
        <p className="q-note">Each career family in the source research carries a RIASEC alignment, so this code is those alignments added up and weighted by how well each family matched you — it is not a separate interest questionnaire. RIASEC describes what interests you; this profiler measures how you think. Treat the three letters as directions worth exploring, and note that Conventional appears in none of the source alignments, so it can never come up here.</p>
      </>}
      <p style={{ fontSize: 13, color: 'var(--muted-foreground)' }}>Branching depth: you reached {d.reached} of {Object.keys(BRANCH_DIM).length} follow-up paths; deeper paths make that dimension's score more reliable.
        {(st.recon !== null || st.tie) && ' We also asked a clarifying question where your answers were ambiguous.'}{!st.recon && !st.tie && amb.tie ? '' : ''}</p>
      <References />
      <div className="q-foot flex gap-3 flex-wrap">
        <Button onClick={() => go('mentor')}>Ask Yuki about my results <ArrowRight /></Button>
        <Button variant="outline" onClick={() => go('careers')}>Explore careers</Button>
        <Button variant="ghost" onClick={() => dispatch({ type: 'dnaReset' })}><RotateCcw />Retake</Button>
      </div>
    </section>, 'qt-1');
}
