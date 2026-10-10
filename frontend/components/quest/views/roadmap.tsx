'use client';
import { useEffect, useRef, useState } from 'react';
import { Check, ExternalLink, Map } from 'lucide-react';
import { useProgress } from '@/components/providers/progress-provider';
import { Owl } from '@/components/quest/common';
import { CAREERS } from '@/lib/data/careers';
import { buildRoadmap, onetUrl } from '@/lib/roadmap';
import { XP_PER_TASK } from '@/lib/scoring';
import { DIMS, profile } from '@/lib/dna';

type Pt = { x: number; y: number };

export function RoadmapView() {
  const { progress, ranked, dispatch, profiled } = useProgress();
  const careerId = progress.planCareer ?? ranked[0]!.career.id;
  const career = CAREERS.find(c => c.id === careerId) ?? CAREERS[0]!;
  const done = progress.tasks[career.id] ?? [];
  const weeks = buildRoadmap(career);

  const total = weeks.reduce((n, w) => n + w.tasks.length, 0);
  const counts = weeks.map(w => ({ complete: w.tasks.filter(t => done.includes(t.id)).length, total: w.tasks.length }));
  const current = counts.findIndex(c => c.complete < c.total);
  // How far along the trail to blaze. The path has one segment per gap between nodes, so dividing by
  // the node count would stop short of the node you're standing on.
  const segments = Math.max(1, weeks.length - 1);
  const blaze = current === -1 ? 1 : (current + counts[current].complete / counts[current].total) / segments;
  const R = 46, C = 2 * Math.PI * R;
  const pct = total ? done.length / total : 0;

  // The two strongest axes from the finished profiler, shown as what they bring to this plan.
  const strengths = profiled ? profile(progress.dna).slice(0, 2).map(r => DIMS[r.key].label) : [];

  // Yuki reacts to where the plan actually is — no invented milestones.
  const yuki = (() => {
    if (done.length === 0) return 'Pick one small step. That’s enough for today.';
    if (done.length === total) return 'All twelve steps. That’s a plan you carried all the way through.';
    const finished = counts.filter(c => c.complete === c.total).length;
    if (finished >= 2) return `${finished} weeks behind you. Notice which steps felt easier than you expected.`;
    if (counts[current]?.complete === 0) return 'This week is next. Start with the step that sounds most interesting.';
    return 'Good progress. Finish this week before adding anything new.';
  })();

  // The trail is drawn through the real node positions, so it stays correct however the text wraps.
  const trailRef = useRef<HTMLDivElement>(null);
  const nodeRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const [trail, setTrail] = useState<{ d: string; w: number; h: number } | null>(null);

  // "+10 XP" floats off the step that was just completed.
  const [flash, setFlash] = useState<string | null>(null);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => { if (flashTimer.current) clearTimeout(flashTimer.current); }, []);
  const toggle = (taskId: string, on: boolean) => {
    dispatch({ type: 'toggleTask', careerId: career.id, taskId });
    if (on) return; // `on` is the state before this click, so true means we just un-completed it
    setFlash(taskId);
    if (flashTimer.current) clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setFlash(f => (f === taskId ? null : f)), 1200);
  };

  useEffect(() => {
    const host = trailRef.current;
    if (!host) return;
    const measure = () => {
      const box = host.getBoundingClientRect();
      const pts = nodeRefs.current.map(el => {
        if (!el) return null;
        const b = el.getBoundingClientRect();
        return { x: b.left - box.left + b.width / 2, y: b.top - box.top + b.height / 2 };
      }).filter((p): p is Pt => p !== null);
      if (pts.length < 2) return setTrail(null);
      let d = `M ${pts[0].x} ${pts[0].y}`;
      for (let i = 1; i < pts.length; i++) {
        const a = pts[i - 1], b = pts[i], mid = (a.y + b.y) / 2;
        d += ` C ${a.x} ${mid}, ${b.x} ${mid}, ${b.x} ${b.y}`;
      }
      setTrail({ d, w: Math.ceil(box.width), h: Math.ceil(box.height) });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(host);
    window.addEventListener('resize', measure);
    return () => { ro.disconnect(); window.removeEventListener('resize', measure); };
  }, [career.id, weeks.length, done.length]);

  return <section className={`workspace roadmap rm-${career.tone}`}>
    <header className="rm-hero">
      <div className="rm-hero-copy">
        <div className="eyebrow"><Map size={14} />Your 30-day career roadmap</div>
        <h2>Your next chapter: {career.name}</h2>
        <p>A flexible starting plan. Make it yours as you learn more. <a className="text-primary underline inline-flex items-center gap-1" href={onetUrl(career)} target="_blank" rel="noreferrer">Real task data on O*NET <ExternalLink size={13} /></a></p>
        {strengths.length > 0 && <p className="rm-strengths">From your Learning DNA: <strong>{strengths.join(' · ')}</strong></p>}
        <label className="rm-pick">My direction
          <select value={career.id} onChange={e => dispatch({ type: 'planCareer', careerId: e.target.value })} className="rounded-md border bg-background p-2 text-foreground">{CAREERS.map(c => <option value={c.id} key={c.id}>{c.name}</option>)}</select>
        </label>
      </div>
      <div className="rm-ring">
        <svg viewBox="0 0 120 120" aria-hidden="true">
          <circle className="rm-ring-track" cx="60" cy="60" r={R} />
          <circle className="rm-ring-fill" cx="60" cy="60" r={R} transform="rotate(-90 60 60)" strokeDasharray={C} strokeDashoffset={C * (1 - pct)} />
        </svg>
        <span className="rm-ring-label" role="img" aria-label={done.length ? `${done.length} of ${total} steps complete` : 'No steps complete yet'}>
          {done.length === 0
            ? <><strong className="rm-ring-start">Begin</strong><span>your first step</span></>
            : <><strong>{done.length}</strong><span>of {total} steps</span></>}
        </span>
      </div>
    </header>

    <div className="rm-yuki">
      <span className="rm-yuki-face"><Owl /></span>
      <p>{yuki}</p>
    </div>

    <div className="rm-trail" ref={trailRef}>
      {trail && <svg className="rm-trail-svg" width={trail.w} height={trail.h} aria-hidden="true">
        <path className="rm-path-base" d={trail.d} pathLength={1} />
        <path className="rm-path-blaze" d={trail.d} pathLength={1} style={{ strokeDasharray: 1, strokeDashoffset: 1 - blaze }} />
      </svg>}

      <ol className="rm-weeks">
        {weeks.map((week, i) => {
          const c = counts[i];
          const finished = c.complete === c.total;
          const state = finished ? 'done' : i === current ? 'now' : 'next';
          const arc = c.total ? c.complete / c.total : 0;
          return <li className={`rm-week ${state}`} key={week.id} style={{ animationDelay: `${i * 70}ms` }}>
            <span className="rm-node" ref={el => { nodeRefs.current[i] = el; }}>
              <svg viewBox="0 0 48 48" aria-hidden="true">
                <circle className="rm-node-track" cx="24" cy="24" r="21" />
                <circle className="rm-node-arc" cx="24" cy="24" r="21" pathLength={1} strokeDasharray={1}
                  strokeDashoffset={1 - arc} transform="rotate(-90 24 24)" />
              </svg>
              <b>{finished ? <Check /> : i + 1}</b>
            </span>
            <div className="rm-card">
              <div className="rm-card-head">
                <h3>Week {i + 1}: {week.title}</h3>
                <span className="rm-count">{c.complete}/{c.total}</span>
              </div>
              <p>{week.description}</p>
              <div className="rm-steps">
                {week.tasks.map(task => {
                  const on = done.includes(task.id);
                  return <label className={`rm-step${on ? ' on' : ''}`} key={task.id}>
                    <input type="checkbox" checked={on} onChange={() => toggle(task.id, on)} />
                    <span className="rm-step-text">{task.text}</span>
                    <span className="rm-step-xp">+{XP_PER_TASK} XP</span>
                    <span className="rm-step-mark" aria-hidden="true"><Check /></span>
                    {flash === task.id && <span className="rm-xp-float" aria-hidden="true">+{XP_PER_TASK} XP</span>}
                  </label>;
                })}
              </div>
            </div>
          </li>;
        })}
      </ol>
    </div>

    <p className="text-xs mt-4">Week 4 covers days 22–30. Your progress is saved for each career.</p>
  </section>;
}
