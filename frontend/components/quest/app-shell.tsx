'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowRight, Brain, ChartNoAxesCombined, Heart, MessageCircle, BookOpen, Check, ChevronRight, Compass, HelpCircle, Home, Lightbulb, Menu, Palette, Play, Route, ShieldCheck, SlidersHorizontal, Sprout, Star, Target, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { useAuth } from '@/components/providers/auth-provider';
import { useProgress } from '@/components/providers/progress-provider';
import { CareerIcon, NavContext, Owl, type NavApi, type View } from '@/components/quest/common';
import { JourneyView } from '@/components/quest/views/journey';
import { CareersView } from '@/components/quest/views/careers';
import { SimulationView } from '@/components/quest/views/simulation';
import { ReflectionView } from '@/components/quest/views/reflection';
import { RoadmapView } from '@/components/quest/views/roadmap';
import { ProfileView } from '@/components/quest/views/profile';
import { ProfilerView } from '@/components/quest/views/profiler';
import { InterestsView } from '@/components/quest/views/interests';
import { IkigaiView } from '@/components/quest/views/ikigai';
import { MentorView } from '@/components/quest/views/mentor';
import { References } from '@/components/quest/references';
import { careerById } from '@/lib/data/careers';
import { CHARACTERS } from '@/lib/data/characters';
import { onetUrl } from '@/lib/roadmap';
import { cn } from '@/lib/utils';

const NAV = [
  { id: 'journey', label: 'My journey', icon: Compass },
  { id: 'careers', label: 'Explore careers', icon: Target },
  { id: 'simulation', label: 'Career simulations', icon: Play },
  { id: 'reflection', label: 'My reflections', icon: BookOpen },
  { id: 'plan', label: 'My roadmap', icon: Route },
  { id: 'profiler', label: 'Learning DNA', icon: Brain },
  { id: 'interests', label: 'My interests', icon: Heart },
  { id: 'ikigai', label: 'Ikigai map', icon: ChartNoAxesCombined },
  { id: 'mentor', label: 'Ask Yuki (AI)', icon: MessageCircle },
  { id: 'profile', label: 'Profile & badges', icon: Star },
] as const;

const HEADINGS: Record<View, [string, string]> = {
  journey: ['Your next chapter starts with you.', 'A little curiosity today. A world of possibilities tomorrow.'],
  careers: ['A world of paths to explore.', 'Follow your curiosity, not just a job title.'],
  simulation: ['Step into a different kind of day.', 'Try the work. Make a decision. Notice how you feel.'],
  reflection: ['Your path is taking shape.', 'Real experiences reveal more than a first impression.'],
  plan: ['Small steps. Meaningful possibilities.', 'Turn a little curiosity into your next 30 days.'],
  profiler: ['Discover how you think.', 'Branching stories reveal your strengths. Follow-ups adapt to you.'],
  interests: ['Discover what you enjoy.', 'Rate the activities that sound energizing to you.'],
  ikigai: ['Explore your Ikigai map.', 'See where your interests, strengths, demand and pay overlap.'],
  mentor: ['Ask Yuki anything.', 'Answers grounded in the research behind your profile.'],
  profile: ['Your quest, your pace.', 'Badges, character, and everything you’ve saved.'],
};

type Modal = 'methodology' | 'palette' | 'help' | 'privacy' | 'career' | null;
const isView = (v: string): v is View => NAV.some(n => n.id === v);

export function AppShell() {
  const { user } = useAuth();
  const { progress, xp, level, profiled, ranked, loaded, dispatch } = useProgress();
  const [view, setView] = useState<View>('journey');
  const [simCareer, setSimCareer] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [modal, setModal] = useState<Modal>(null);
  const [careerId, setCareerId] = useState<string>('design');

  // Keep the URL hash in sync so refresh and the back button work.
  useEffect(() => {
    const sync = () => { const h = window.location.hash.slice(1); if (isView(h)) setView(h); };
    sync();
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);

  const go = useCallback((next: View) => {
    window.location.hash = next;
    setView(next);
    setMobileOpen(false);
    window.scrollTo({ top: 0 });
  }, []);

  const nav = useMemo<NavApi>(() => ({
    view, go, simCareer,
    startSim: id => { setSimCareer(id); setModal(null); go('simulation'); },
    openCareer: id => { setCareerId(id); setModal('career'); dispatch({ type: 'explored', careerId: id }); },
    openModal: m => setModal(m),
  }), [view, go, simCareer, dispatch]);

  if (!user || !loaded) return null;
  const character = progress.character !== null ? CHARACTERS[progress.character] : null;
  const career = careerById(careerId)!;
  const initials = character?.initials ?? user.name.slice(0, 2).toUpperCase();
  const avatar = character ? <img src={character.image} alt="" /> : initials;
  const label = NAV.find(n => n.id === view)?.label;

  // The questionnaire takes over the whole screen: no sidebar, navigation, references or footer.
  if (view === 'profiler') return <NavContext.Provider value={nav}><ProfilerView /></NavContext.Provider>;

  return <NavContext.Provider value={nav}>
    <div className="app-shell">
      <aside className={cn('sidebar', mobileOpen && 'open')}>
        <div className="logo"><div className="logo-mark"><Sprout size={22} /></div><div>Career<span className="accent">Quest</span></div></div>
        <div className="sidebar-label">Your adventure</div>
        <nav className="side-nav" aria-label="Main navigation">{NAV.map(item => <Button key={item.id} variant="ghost" className={cn('nav-item', view === item.id && 'active')} aria-current={view === item.id ? 'page' : undefined} onClick={() => { if (item.id === 'simulation') setSimCareer(null); go(item.id); }}><item.icon />{item.label}</Button>)}</nav>
        <div className="sidebar-bottom">
          <div className="level-card"><strong>Level {level.level} · {level.title}</strong><div className="level-bar"><div style={{ width: `${level.intoLevel / level.perLevel * 100}%` }} /></div><small>{level.perLevel - level.intoLevel} XP to next level</small></div>
          <nav className="side-nav" aria-label="More">
            <Button variant="ghost" className="nav-item" onClick={() => setModal('palette')}><Palette />Colors & inspiration</Button>
            <Button variant="ghost" className="nav-item" onClick={() => setModal('privacy')}><SlidersHorizontal />Privacy</Button>
            <Button variant="ghost" className="nav-item" onClick={() => setModal('help')}><HelpCircle />Help from Yuki</Button>
          </nav>
          <div className="sidebar-footer"><div className="avatar">{avatar}</div><div><strong>{user.name}</strong><small>{user.guest ? 'Guest mode' : character?.name ?? 'Your story, unfolding'}</small></div></div>
        </div>
      </aside>
      <div className={cn('scrim', mobileOpen && 'open')} onClick={() => setMobileOpen(false)} aria-hidden="true" />
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <Button aria-label={mobileOpen ? 'Close navigation' : 'Open navigation'} variant="ghost" size="icon" className="mobile-menu" onClick={() => setMobileOpen(!mobileOpen)}>{mobileOpen ? <X /> : <Menu />}</Button>
            <Home size={14} /><span>Your adventure</span><ChevronRight size={12} /><strong>{label}</strong>
          </div>
          <div className="top-actions"><span className="xp" aria-label={`${xp} experience points`}><Star />{xp} XP</span><button className="avatar" aria-label="Open profile" onClick={() => go('profile')} style={{ border: 0 }}>{avatar}</button></div>
        </header>
        <main className="main-content">
          <div className="page-heading"><div><h1>{HEADINGS[view][0]}</h1><p>{HEADINGS[view][1]}</p></div><span className="chip">{profiled ? 'Chapter 2 · Explore your world' : 'Chapter 1 · Discover yourself'}</span></div>
          <div className="fade-in" key={view}>
            {view === 'journey' && <JourneyView />}
            {view === 'careers' && <CareersView />}
            {view === 'simulation' && <SimulationView />}
            {view === 'reflection' && <ReflectionView />}
            {view === 'plan' && <RoadmapView />}
            {view === 'profile' && <ProfileView />}
            {view === 'interests' && <InterestsView />}
            {view === 'ikigai' && <IkigaiView />}
            {view === 'mentor' && <MentorView />}
          </div>
          <References />
          <footer className="bottom-note"><span>Made for possibilities, not boxes. Your journey is uniquely yours.</span><Button variant="link" className="text-action" onClick={() => setModal('methodology')}><ShieldCheck />Our sources & methodology <ArrowRight /></Button></footer>
        </main>
      </div>
      <Dialog open={modal !== null} onOpenChange={o => !o && setModal(null)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{modal === 'palette' ? 'The CareerQuest palette' : modal === 'career' ? career.name : modal === 'privacy' ? 'Your journey, your privacy' : modal === 'help' ? 'A little guidance from Yuki' : 'A path, not a prediction'}</DialogTitle>
            <DialogDescription>{modal === 'palette' ? 'Fresh, optimistic, and a little playful.' : modal === 'career' ? career.category : modal === 'privacy' ? 'What’s saved, and where.' : modal === 'methodology' ? 'Transparent about what this prototype can and can’t tell you.' : 'Keep exploring at your own pace.'}</DialogDescription>
          </DialogHeader>
          {modal === 'palette' && <><div className="palette-grid">{[['Deep teal', '#277E75', 'bg-primary'], ['Soft mint', '#E2F4E9', 'bg-mint'], ['Peach coral', '#FCE7DE', 'bg-coral'], ['Sunshine', '#FFF0BE', 'bg-yellow'], ['Soft lilac', '#EEE6F6', 'bg-lilac']].map(([n, c, t]) => <div key={n}><div className={`swatch ${t}`} /><div className="swatch-label">{n}</div><div className="swatch-code">{c}</div></div>)}</div><p className="text-sm text-muted-foreground leading-7">Teal anchors your journey. Mint feels open and calm; coral, sunshine, and lilac give each character personality. Manrope headings and DM Sans body text keep it friendly and readable.</p></>}
          {modal === 'methodology' && <div className="space-y-4 text-sm leading-7">
            <p><strong>Explore careers.</strong> The existing character and simulation preference ranking is exploratory and separate from the Ikigai map. It no longer uses hand-entered market or pay values.</p>
            <p><strong>Ikigai evidence.</strong> Love combines the original 18-item RIASEC screening set with enjoyment feedback. Good at combines Learning DNA answers with O*NET 31.0 occupational requirements and simulation confidence. This short screener and the Learning DNA crosswalk are modelling assumptions, not validated career assessments.</p>
            <p><strong>Market and pay.</strong> US needs uses BLS 2025–35 projected growth and annual openings; paid uses BLS 2025 median annual wage. Pakistan uses ILOSTAT 2021–25 employment change and 2025 employment level by broad ISCO-08 group; pay uses 2025 major-group median hourly PKR. Broad Pakistani groups repeat across several careers. These are employment estimates, not posting counts or vacancies.</p>
            <p><strong>Cost context.</strong> Numbeo's 2026 Mid-Year Cost of Living Plus Rent Index is shown by country. It does not change within-country career ranks and is not a purchasing-power conversion.</p>
            <p><strong>Missing evidence.</strong> Unanswered personal sections remain unavailable. An overall four-circle score appears only when all four circles have evidence. Notes about grades, projects and social impact are not numerically scored until validated data can support them.</p>
            <p>Read the <a href="https://www.onetcenter.org/database.html" target="_blank" rel="noreferrer" className="text-primary underline">O*NET data</a>, <a href="https://www.bls.gov/emp/tables/occupational-separations-and-openings.htm" target="_blank" rel="noreferrer" className="text-primary underline">BLS projections</a>, <a href="https://ilostat.ilo.org/data/" target="_blank" rel="noreferrer" className="text-primary underline">ILOSTAT</a> and <a href="https://www.onetcenter.org/reports/IP_RVS.html" target="_blank" rel="noreferrer" className="text-primary underline">Interest Profiler research</a>.</p>
          </div>}
          {modal === 'help' && <div className="space-y-4"><div className="sensei-top"><div className="owl"><Owl /></div><div><h3>Yuki · Your discovery sensei</h3><p>Small steps are still steps.</p></div></div><p className="text-sm text-muted-foreground leading-7">“Choose the character you relate to today. Explore your Learning DNA, try a day in a career, and notice how the work feels. You’re allowed to change your mind.”</p><Button onClick={() => { setModal(null); go('profiler'); }}>Start the Learning DNA profiler <ArrowRight /></Button></div>}
          {modal === 'privacy' && <p className="text-sm text-muted-foreground leading-7">Your character, profile answers, ratings, journal, and progress are saved to your account so they follow you across devices. In guest mode they stay in this browser only. You can export, reset, or delete everything from Profile.</p>}
          {modal === 'career' && <div className="space-y-5">
            <div className="flex items-center gap-3"><CareerIcon career={career} /><p className="text-sm leading-7 text-muted-foreground">{career.description}</p></div>
            <div><h3 className="text-sm font-bold mb-3">What the work can look like</h3><ul className="space-y-3">{career.tasks.map(t => <li className="flex gap-2 text-sm" key={t}><Check size={16} className="text-primary shrink-0 mt-0.5" />{t}</li>)}</ul></div>
            <div className="sensei-tip"><Lightbulb /><div><strong>Reality check</strong><p>{career.reality}</p></div></div>
            <div className="sensei-tip"><Lightbulb /><div><strong>How AI may change it</strong><p>{career.aiNote}</p></div></div>
            <span className="small-tag">Hand-written summary · <a className="underline" href={onetUrl(career)} target="_blank" rel="noreferrer">Check O*NET</a></span>
            <div className="flex gap-3 flex-wrap"><Button onClick={() => nav.startSim(career.id)}><Play />Try a day in the life</Button><Button variant="outline" onClick={() => { dispatch({ type: 'planCareer', careerId: career.id }); setModal(null); go('plan'); }}>Build a roadmap <ArrowRight /></Button></div>
          </div>}
        </DialogContent>
      </Dialog>
    </div>
  </NavContext.Provider>;
}
