'use client';
import { useState, type FormEvent } from 'react';
import { Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/components/providers/auth-provider';
import { useProgress } from '@/components/providers/progress-provider';
import { askYuki } from '@/lib/rag';

export function MentorView() {
  const { user } = useAuth();
  const { progress, dispatch } = useProgress();
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);

  if (!user || user.guest) return <section className="sensei-panel"><h2>Sign in to chat with Yuki</h2><p>The mentor uses your account to keep answers private and personal. Log in or create an account from the menu.</p></section>;

  const send = async (e: FormEvent) => {
    e.preventDefault();
    const question = q.trim();
    if (!question || busy) return;
    dispatch({ type: 'mentorMessage', message: { id: crypto.randomUUID(), at: new Date().toISOString(), role: 'you', text: question } });
    setQ(''); setBusy(true);
    try {
      const r = await askYuki(question, progress);
      const text = r.answer ?? (r.status === 'not_configured' ? 'The AI key isn’t set up on the server yet, so here are the closest passages I found.' : r.status === 'unavailable' ? 'The mentor is temporarily unavailable. Please try again.' : 'I couldn’t find that in the research behind your profile. Try rephrasing.');
      dispatch({ type: 'mentorMessage', message: { id: crypto.randomUUID(), at: new Date().toISOString(), role: 'yuki', text: text.slice(0, 4000), sources: r.sources.slice(0, 6).map(source => ({ ...source, title: source.title.slice(0, 200), excerpt: source.excerpt.slice(0, 600) })) } });
    } catch (err) {
      dispatch({ type: 'mentorMessage', message: { id: crypto.randomUUID(), at: new Date().toISOString(), role: 'yuki', text: err instanceof Error ? err.message : 'Something went wrong.' } });
    }
    setBusy(false);
  };

  return <section className="sensei-panel" aria-live="polite">
    <p style={{ fontSize: 13 }}>Try: “Why was I asked about the unfamiliar city?” or “What careers fit my strengths?”</p>
    <div style={{ display: 'grid', gap: 12, margin: '14px 0' }}>{progress.mentorMessages.map(m => <div key={m.id} style={{ justifySelf: m.role === 'you' ? 'end' : 'start', maxWidth: '92%' }}>
      <div style={{ padding: '10px 14px', borderRadius: 12, border: '1px solid var(--border)', whiteSpace: 'pre-wrap' }}>{m.text}</div>
      {m.sources && m.sources.length > 0 && <details style={{ fontSize: 12, marginTop: 4 }}><summary style={{ cursor: 'pointer' }}>Sources ({m.sources.length})</summary>
        <ol style={{ paddingLeft: 18 }}>{m.sources.map(s => <li key={s.n} value={s.n}><strong>{s.title}</strong>: {s.excerpt}</li>)}</ol></details>}
    </div>)}{busy && <em>Yuki is thinking…</em>}</div>
    <form onSubmit={send} style={{ display: 'flex', gap: 8 }}>
      <input className="text-input" style={{ flex: 1 }} value={q} onChange={e => setQ(e.target.value)} maxLength={1000} placeholder="Ask about your results, the questions, or careers" aria-label="Your question" />
      <Button type="submit" disabled={busy || !q.trim()}><Send />Ask</Button>
    </form>
  </section>;
}
