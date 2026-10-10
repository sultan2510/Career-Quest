'use client';
import { useProgress } from '@/components/providers/progress-provider';
import { useNav } from '@/components/quest/common';
import { Button } from '@/components/ui/button';
import { INTEREST_ITEMS, RIASEC, interestScores } from '@/lib/interests';

export function InterestsView() {
  const { progress, dispatch } = useProgress();
  const { go } = useNav();
  const count = INTEREST_ITEMS.filter(item => progress.interests[item.id] >= 1).length;
  const scores = interestScores(progress.interests);

  return <div className="stack">
    <section className="workspace">
      <h2 style={{ marginTop: 0 }}>What work do you enjoy?</h2>
      <p>Rate 18 activities from 1 (strongly dislike) to 5 (strongly like). Think about the work itself, not the training or pay. This short screening set is exploratory and is not the validated O*NET Interest Profiler.</p>
      <p role="status">{count} of {INTEREST_ITEMS.length} answered</p>
      {RIASEC.map(kind => <fieldset key={kind} style={{ border: 0, padding: 0, margin: '20px 0' }}>
        <legend style={{ fontWeight: 700, marginBottom: 8 }}>{kind}</legend>
        {INTEREST_ITEMS.filter(item => item.kind === kind).map(item => <div key={item.id} style={{ marginBottom: 14 }}>
          <label htmlFor={`interest-${item.id}`}>{item.text}</label>
          <select id={`interest-${item.id}`} className="text-input" style={{ display: 'block', maxWidth: 230 }} value={progress.interests[item.id] ?? ''} onChange={event => dispatch({ type: 'interestAnswer', id: item.id, rating: Number(event.target.value) })}>
            <option value="">Choose a rating</option>
            <option value="1">1 · Strongly dislike</option><option value="2">2 · Dislike</option><option value="3">3 · Neutral</option><option value="4">4 · Like</option><option value="5">5 · Strongly like</option>
          </select>
        </div>)}
      </fieldset>)}
      <label htmlFor="stated-interests">Other interests you want to remember</label>
      <textarea id="stated-interests" className="custom-answer" maxLength={500} value={progress.statedInterests} onChange={event => dispatch({ type: 'statedInterests', text: event.target.value })} />
      <p className="text-sm">Your notes are saved as context and do not change the numeric interest score.</p>
      <Button onClick={() => go('ikigai')} disabled={count !== INTEREST_ITEMS.length}>See my Ikigai map</Button>
    </section>
    {Object.keys(scores).length === RIASEC.length && <section className="workspace"><h3>Your interest pattern</h3>
      {RIASEC.map(kind => <p key={kind}>{kind}: {Math.round((scores[kind] ?? 0) * 100)}%</p>)}
    </section>}
  </div>;
}
