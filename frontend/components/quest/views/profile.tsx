'use client';
import { useState } from 'react';
import { Award, Download, LogOut, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { useAuth } from '@/components/providers/auth-provider';
import { useProgress } from '@/components/providers/progress-provider';
import { CharacterCards } from '@/components/quest/common';
import { buildReport, download } from '@/lib/report';

export function ProfileView() {
  const { user, rename, logOut, deleteAccount, openAuth } = useAuth();
  const { progress, resetProgress, retrySave, badges, level, xp } = useProgress();
  const [name, setName] = useState(user?.name ?? '');
  const [confirm, setConfirm] = useState<'reset' | 'delete' | null>(null);
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState(false);
  if (!user) return null;
  const earned = badges.filter(b => b.earned).length;

  const leave = async () => {
    setActionError(''); setBusy(true);
    try { await retrySave(); await logOut(); }
    catch (cause) { setActionError(cause instanceof Error ? cause.message : 'Could not end the session. Please try again.'); }
    finally { setBusy(false); }
  };

  const confirmAction = async () => {
    setActionError(''); setBusy(true);
    try {
      if (confirm === 'delete') await deleteAccount();
      else await resetProgress();
      setConfirm(null);
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : 'Could not save the change. Please try again.');
    } finally { setBusy(false); }
  };

  return <div className="stack">
    {user.guest && <div className="banner"><span>Your guest work is saved privately in the database for this browser. Create an account to access it on other devices.</span><Button size="sm" onClick={() => openAuth('signup')}>Create account</Button></div>}
    {actionError && <div className="form-error" role="alert">{actionError}</div>}
    <section className="workspace">
      <h2 style={{ marginTop: 0 }}>Level {level.level} {level.title}</h2>
      <div className="quest-progress" style={{ marginTop: 0 }}><div className="progress-track"><div className="progress-fill" style={{ width: `${level.intoLevel / level.perLevel * 100}%` }} /></div><span>{xp} XP</span></div>
      {!user.guest && <div className="field" style={{ maxWidth: 360 }}><label htmlFor="display-name">Display name</label><div className="flex gap-2"><input id="display-name" className="text-input" value={name} onChange={e => setName(e.target.value)} /><Button variant="outline" disabled={name.trim().length < 2 || name.trim() === user.name} onClick={() => rename(name)}>Save</Button></div><span className="hint">{user.email}</span></div>}
    </section>
    <section className="workspace">
      <div className="eyebrow"><Award size={14} />Badges · {earned} of {badges.length}</div>
      <div className="badge-grid mt-4">{badges.map(b => <div key={b.id} className={`badge ${b.earned ? 'earned' : ''}`}><div className="medal"><Award size={20} /></div><strong>{b.name}</strong><small>{b.earned ? 'Earned' : b.hint}</small></div>)}</div>
    </section>
    <section className="workspace"><h2 style={{ marginTop: 0 }}>Your character</h2><p>Switch any time. Your Learning DNA profile stays the same.</p><CharacterCards compact /></section>
    <section className="workspace">
      <h2 style={{ marginTop: 0 }}>Your data</h2>
      <div className="pill-row">
        <Button variant="outline" onClick={() => download('careerquest-report.md', buildReport(user.name, progress))}><Download />Download my report</Button>
        <Button variant="outline" onClick={() => download('careerquest-data.json', JSON.stringify(progress, null, 2), 'application/json')}><Download />Export my data</Button>
        <Button variant="outline" onClick={() => setConfirm('reset')}>Reset my progress</Button>
        <Button variant="outline" disabled={busy} onClick={() => void leave()}><LogOut />{user.guest ? 'Leave guest mode' : 'Log out'}</Button>
        <Button variant="outline" disabled={busy} onClick={() => setConfirm('delete')}><Trash2 />{user.guest ? 'Delete guest data' : 'Delete account'}</Button>
      </div>
    </section>
    <Dialog open={confirm !== null} onOpenChange={o => !o && setConfirm(null)}>
      <DialogContent>
        <DialogHeader><DialogTitle>{confirm === 'delete' ? (user.guest ? 'Delete your guest data?' : 'Delete your account?') : 'Reset your progress?'}</DialogTitle><DialogDescription>{confirm === 'delete' ? 'This permanently removes this session and everything saved to it. It can’t be undone.' : 'This clears your character, answers, simulations, journal, and roadmap. Your session stays.'}</DialogDescription></DialogHeader>
        <div className="flex gap-3 justify-end"><Button variant="outline" disabled={busy} onClick={() => setConfirm(null)}>Cancel</Button><Button disabled={busy} onClick={() => void confirmAction()}>{busy ? 'Saving…' : confirm === 'delete' ? (user.guest ? 'Delete guest data' : 'Delete account') : 'Reset progress'}</Button></div>
      </DialogContent>
    </Dialog>
  </div>;
}
