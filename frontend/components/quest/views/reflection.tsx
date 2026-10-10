'use client';
import { useEffect, useState } from 'react';
import { ArrowRight, BookOpen, Play, Trash2, TrendingUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useProgress } from '@/components/providers/progress-provider';
import { useNav } from '@/components/quest/common';
import { careerById } from '@/lib/data/careers';
import { CHARACTERS } from '@/lib/data/characters';
import { JOURNAL_PROMPTS } from '@/lib/roadmap';
import { classifyEvidence } from '@/lib/scoring';

/** Which step of the fit ramp a score sits on. The colour states the value, not the career. */
const bandOf = (n: number) => (n >= 80 ? 'd' : n >= 70 ? 'c' : n >= 60 ? 'b' : 'a');

/** A half-dial reading 0–100. Animates from empty on mount, so a change in score is visible as movement. */
function Gauge({ value, id }: { value: number; id: string }) {
  const R = 34, CX = 44, CY = 42;
  const at = (pct: number) => {
    const rad = Math.PI * (1 - pct / 100);
    return [CX + R * Math.cos(rad), CY - R * Math.sin(rad)] as const;
  };
  const [ex, ey] = at(value);
  const [nx, ny] = at(value);
  const k = 0.78;
  const [ready, setReady] = useState(false);
  useEffect(() => { const r = requestAnimationFrame(() => setReady(true)); return () => cancelAnimationFrame(r); }, []);
  const ease = 'cubic-bezier(.2,.7,.3,1) .95s';
  return <svg className="rf-gauge-svg" viewBox="0 0 88 56" aria-hidden="true">
    <defs>
      {/* var() does not resolve in an SVG attribute, but it does in a style declaration. */}
      <linearGradient id={`rf-grad-${id}`} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" style={{ stopColor: 'var(--rf-tone)' }} />
        <stop offset="100%" style={{ stopColor: 'var(--rf-tone)', stopOpacity: 0.5 }} />
      </linearGradient>
    </defs>
    <path className="rf-gauge-track" d={`M ${CX - R} ${CY} A ${R} ${R} 0 0 1 ${CX + R} ${CY}`} />
    <path className="rf-gauge-value" d={`M ${CX - R} ${CY} A ${R} ${R} 0 0 1 ${ex} ${ey}`} stroke={`url(#rf-grad-${id})`}
      pathLength={1} strokeDasharray={1} strokeDashoffset={ready ? 0 : 1} style={{ transition: `stroke-dashoffset ${ease}` }} />
    <line className="rf-gauge-base" x1={CX - 15} y1={CY} x2={CX + 15} y2={CY} />
    <line className="rf-gauge-needle" x1={CX} y1={CY} x2={CX + (nx - CX) * k} y2={CY + (ny - CY) * k}
      style={{ transformBox: 'view-box', transformOrigin: `${CX}px ${CY}px`, transform: ready ? 'none' : `rotate(${-value * 1.8}deg)`, transition: `transform ${ease}` }} />
    <circle className="rf-gauge-hub" cx={CX} cy={CY} r="5" />
    <circle className="rf-gauge-hub-shine" cx={CX - 1.7} cy={CY - 1.7} r="1.7" />
  </svg>;
}

export function ReflectionView() {
  const { progress, ranked, profiled, dispatch } = useProgress();
  const { go, startSim } = useNav();
  const [text, setText] = useState('');
  const prompt = JOURNAL_PROMPTS[progress.journal.length % JOURNAL_PROMPTS.length]!;
  const last = progress.evidence[progress.evidence.length - 1];
  const lastCareer = last ? careerById(last.careerId) : undefined;
  const top = ranked.slice(0, 5);

  // Nothing has moved until a simulation lands, so the "now" positions and the point deltas stay hidden
  // until then rather than showing five identical dials and a column of zeros.
  const changed = ranked.some(r => r.delta !== 0);
  const firstRun = progress.evidence.length === 0;
  // Remount the dials whenever the scores actually move, so they re-animate on a real change only.
  const signature = top.map(r => `${r.baseline.overall}-${r.score.overall}`).join('|');

  return <div className="stack">
    <div className="detail-grid">
      <section className="workspace rf-panel">
        <div className="eyebrow"><TrendingUp size={14} />Your evolving career fit</div>
        <h2>{changed ? 'Experience changes the picture.' : 'Where your matches start.'}</h2>
        <p>{changed ? 'Each dial is one career’s match now that your simulations are counted. Its colour and the pill in the corner both read the score.' : 'These are your starting matches. Rate a day in a career and you will see them move.'}</p>

        <div className="rf-gauges" key={signature} role="img"
          aria-label={changed
            ? `Career fit movement for ${top.map(r => `${r.career.name}, ${r.baseline.overall} to ${r.score.overall}`).join('; ')}`
            : `Starting career fit for ${top.map(r => `${r.career.name} at ${r.score.overall}`).join('; ')}`}>
          {top.map(r => {
            const was = r.baseline.overall, now = r.score.overall;
            const dir = now > was ? 'up' : now < was ? 'down' : 'flat';
            return <div className={`rf-gauge band-${bandOf(now)}`} key={r.career.id}>
              {changed && <span className={`rf-gauge-delta ${dir}`} aria-hidden="true">{now > was ? '+' : ''}{r.delta}</span>}
              <Gauge value={now} id={r.career.id} />
              <strong className="rf-gauge-name">{r.career.name}</strong>
              <span className="rf-gauge-sub">{changed ? `${was} → ${now}` : `${now}% match`}</span>
            </div>;
          })}
        </div>
        <p className="rf-scale-note" aria-hidden="true">
          <span className="rf-key band-a" />under 60 <span className="rf-key band-b" />60s <span className="rf-key band-c" />70s <span className="rf-key band-d" />80+
        </p>

        {lastCareer && last && <div className="consequence"><strong className="text-sm">Why it moved</strong><p>Your latest {lastCareer.name} day felt {last.enjoyment >= 4 ? 'energizing' : last.enjoyment <= 2 ? 'less enjoyable' : 'neutral'}. Confidence is self-reported, not a measure of skill. Careers that share themes shift a little too.</p></div>}

        <div className="flex gap-3 flex-wrap mt-4">
          {firstRun
            ? <><Button onClick={() => startSim(null)}><Play />Try your first simulation</Button><Button variant="outline" onClick={() => go('plan')}>Build my 30-day plan <ArrowRight /></Button></>
            : <><Button onClick={() => go('plan')}>Build my 30-day plan <ArrowRight /></Button><Button variant="outline" onClick={() => startSim(null)}><Play />Explore another day</Button></>}
        </div>
      </section>

      <section className="workspace">
        <div className="eyebrow"><BookOpen size={14} />Evidence timeline</div>
        <h2>The moments behind your matches</h2>
        <ol className="rf-log">
          <li className="rf-moment">
            <span className="rf-dot" aria-hidden="true">1</span>
            <div className="rf-moment-body">
              <strong>{progress.character !== null ? `${CHARACTERS[progress.character]!.name} selected` : 'No character chosen yet'}</strong>
              <p>Starting preference · Tentative, self-reported</p>
            </div>
          </li>
          {profiled && <li className="rf-moment">
            <span className="rf-dot" aria-hidden="true">2</span>
            <div className="rf-moment-body">
              <strong>Learning DNA profile completed</strong>
              <p>Your branching profiler responses shaped your strength profile.</p>
            </div>
          </li>}
          {[...progress.evidence].reverse().map((ev, i) => {
            const c = classifyEvidence(ev); const career = careerById(ev.careerId);
            return <li className="rf-moment" key={ev.id}>
              <span className="rf-dot" aria-hidden="true">{i + (profiled ? 3 : 2)}</span>
              <div className="rf-moment-body">
                <strong>{career?.name ?? ev.careerId} · Simulation</strong>
                <p><span className="signal">{c.label}</span></p>
                <p>Enjoyment {ev.enjoyment}/5 · Confidence {ev.confidence}/5. {c.note}</p>
                <details className="text-sm mt-2"><summary className="cursor-pointer text-primary">View your decisions</summary>{ev.decisions.map((d, j) => <p key={j}><strong>Scene {d.scene + 1}:</strong> {d.text}</p>)}</details>
              </div>
            </li>;
          })}
        </ol>
      </section>
    </div>

    <section className="workspace rf-journal">
      <div className="eyebrow"><BookOpen size={14} />My journal</div>
      <h2>{prompt}</h2>
      <p className="rf-journal-note">Only you can see this. Nothing here is scored or shared.</p>
      <label htmlFor="journal" className="sr-only">Journal entry</label>
      <textarea id="journal" className="custom-answer rf-textarea" placeholder="Write a few honest sentences." maxLength={1200} value={text} onChange={e => setText(e.target.value)} />
      <div className="rf-write-foot">
        <span className="rf-count">{text.length} / 1200</span>
        <Button disabled={!text.trim()} onClick={() => { dispatch({ type: 'journalAdd', entry: { id: crypto.randomUUID(), at: new Date().toISOString(), prompt, text: text.trim() } }); setText(''); }}>Save entry</Button>
      </div>
      {progress.journal.length === 0
        ? <p className="rf-empty">Nothing written yet. Saving an entry moves the prompt on to the next question.</p>
        : <ul className="rf-entries">{progress.journal.map(e => <li className="rf-entry" key={e.id}>
          <div className="rf-entry-top">
            <span className="rf-entry-date">{new Date(e.at).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}</span>
            <span className="rf-entry-prompt">{e.prompt}</span>
            <Button variant="ghost" size="icon" aria-label="Delete entry" onClick={() => dispatch({ type: 'journalRemove', id: e.id })}><Trash2 /></Button>
          </div>
          <p className="rf-entry-text">{e.text}</p>
        </li>)}</ul>}
    </section>
  </div>;
}
