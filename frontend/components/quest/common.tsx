'use client';
import { createContext, useContext } from 'react';
import { ArrowRight, Check, Lightbulb, Code, GraduationCap, HeartPulse, Leaf, Newspaper, Palette, ChartNoAxesCombined, Rocket } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CHARACTERS } from '@/lib/data/characters';
import { cn } from '@/lib/utils';
import type { Career, IconKey } from '@/lib/types';
import { useProgress } from '@/components/providers/progress-provider';

export type View = 'journey' | 'careers' | 'simulation' | 'reflection' | 'plan' | 'profile' | 'profiler' | 'interests' | 'ikigai' | 'mentor';

export type NavApi = {
  view: View;
  go: (view: View) => void;
  startSim: (careerId: string | null) => void;
  simCareer: string | null;
  openCareer: (careerId: string) => void;
  openModal: (modal: 'methodology' | 'palette' | 'help' | 'privacy') => void;
};
export const NavContext = createContext<NavApi | null>(null);
export const useNav = () => {
  const ctx = useContext(NavContext);
  if (!ctx) throw new Error('useNav must be used inside the app shell');
  return ctx;
};

export function Owl() {
  return <svg viewBox="0 0 60 60" width="36" height="36" aria-hidden="true"><path d="M12 24 10 7 24 16Q30 13 36 16L50 7 48 24Q55 52 30 54Q5 52 12 24Z" fill="var(--primary)" /><ellipse cx="30" cy="36" rx="18" ry="17" fill="var(--yellow)" /><circle cx="22" cy="29" r="10" fill="var(--card)" stroke="var(--foreground)" strokeWidth="2" /><circle cx="39" cy="29" r="10" fill="var(--card)" stroke="var(--foreground)" strokeWidth="2" /><circle cx="23" cy="29" r="3" fill="var(--foreground)" /><circle cx="38" cy="29" r="3" fill="var(--foreground)" /><path d="m27 38 4 5 4-5" fill="var(--coral-strong)" /></svg>;
}

const ICONS: Record<IconKey, typeof Palette> = {
  design: Palette, data: ChartNoAxesCombined, environment: Leaf, software: Code,
  education: GraduationCap, health: HeartPulse, product: Rocket, journalism: Newspaper,
};
export function CareerIcon({ career }: { career: Career }) {
  const Icon = ICONS[career.icon];
  return <div className={cn('career-icon', `tone-${career.tone}`)} aria-hidden="true"><Icon /></div>;
}

export function CareerCard({ career, score, label, picked, onPick }: { career: Career; score: number | null; label: string; picked?: boolean; onPick?: (checked: boolean) => void }) {
  const { openCareer } = useNav();
  return (
    <article className={cn('career-card', picked && 'picked')}>
      <div className="career-top"><CareerIcon career={career} /><span className={cn('fit-badge', score === null && 'muted')}>{score === null ? 'Not matched yet' : `${score}% fit`}</span></div>
      <h3>{career.name}</h3>
      <p className="career-desc">{career.category}</p>
      <div className="career-bottom">
        {onPick ? <label className="compare-check"><input type="checkbox" checked={!!picked} onChange={e => onPick(e.target.checked)} />Compare</label> : <span>{label}</span>}
        <Button variant="link" className="text-action" onClick={() => openCareer(career.id)}>Explore <ArrowRight /></Button>
      </div>
    </article>
  );
}

export function CharacterCards({ compact = false }: { compact?: boolean }) {
  const { progress, dispatch } = useProgress();
  const current = progress.character;
  return (
    <div className="characters">
      {CHARACTERS.map((c, index) => (
        <article className={cn('character-card', current === index && 'selected')} key={c.id}>
          {current === index && <div className="selected-check"><Check /></div>}
          <div className="character-art"><img src={c.image} alt={`${c.name}, an illustrated student mascot`} loading="lazy" width={384} height={768} /></div>
          <div className="character-body">
            <h3>{c.name}</h3><p className="tag">{c.tag}</p>
            {!compact && <p>{c.description}</p>}
            <div className="traits">{c.traits.map(t => <span key={t}>{t}</span>)}</div>
            <Button className="choose" variant={current === index ? 'default' : 'outline'} aria-pressed={current === index} onClick={() => dispatch({ type: 'character', index })}>
              {current === index ? <><Check />That’s me!</> : <>Choose character <ArrowRight /></>}
            </Button>
          </div>
        </article>
      ))}
    </div>
  );
}

export function SenseiPanel({ className = '' }: { className?: string }) {
  const { progress, profiled, ranked } = useProgress();
  const { go, startSim } = useNav();
  const hasEvidence = progress.evidence.length > 0;
  const dnaStarted = Object.keys(progress.dna.answers).length > 0;
  const character = progress.character !== null ? CHARACTERS[progress.character] : null;
  const tip = character ? `${character.name} is a starting point, not a box. Your experiences will help shape your path.` : 'Choose a character that feels like you today. You can always grow into someone new.';
  const next = !profiled
    ? { title: dnaStarted ? 'Pick up your profile' : 'The Learning DNA Profiler', sub: dnaStarted ? 'Your next story is waiting' : '7 short stories · About 10-15 decisions', cta: dnaStarted ? 'Keep going' : 'Discover how you think', run: () => go('profiler') }
    : !hasEvidence
      ? { title: 'Try a day in the life', sub: '2 scenes · A new perspective', cta: 'Try a simulation', run: () => startSim(ranked[0]!.career.id) }
      : { title: 'Plan your next 30 days', sub: '12 small steps · Make it yours', cta: 'Open my roadmap', run: () => go('plan') };
  return (
    <aside className={cn('sensei-panel side', className)}>
      <div className="sensei-top"><div className="owl"><Owl /></div><div><h3>Meet Yuki, your sensei</h3><p>A little wisdom for your journey</p></div></div>
      <p className="sensei-quote">“You don’t have to have it all figured out. Start with what makes you <strong>curious</strong>, and we’ll find the connections together.”</p>
      <div className="sensei-tip"><Lightbulb /><span>{tip}</span></div>
      <div className="next-quest"><div className="label">Your next little adventure</div><h4>{next.title}</h4><p>{next.sub}</p><Button className="quest-button" onClick={next.run}>{next.cta} <ArrowRight /></Button></div>
    </aside>
  );
}
