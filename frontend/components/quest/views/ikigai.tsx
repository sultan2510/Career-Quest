'use client';
import { useMemo, useState } from 'react';
import { useProgress } from '@/components/providers/progress-provider';
import { useNav } from '@/components/quest/common';
import { CAREERS } from '@/lib/data/careers';
import { CIRCLES, EVIDENCE, ikigaiCareers, type Circle } from '@/lib/ikigai';
import { ELLIPSES, placeInRegions } from '@/lib/venn';

const LABEL: Record<Circle, string> = { love: 'Love', good: 'Good at', needs: 'World needs', paid: 'Paid for' };
const COLOR: Record<Circle, string> = { love: '#d6456f', good: '#2f6fcf', needs: '#3c9a5f', paid: '#d9a21b' };
const ZONES: Record<string, string> = {
  'love|good': 'Passion', 'love|needs': 'Mission', 'good|paid': 'Profession', 'needs|paid': 'Vocation',
  'love|good|needs|paid': 'All four',
};
const percent = (n: number | null) => n === null ? 'No evidence' : `${Math.round(n * 100)}%`;

export function IkigaiView() {
  const { progress, dispatch } = useProgress();
  const { go } = useNav();
  const [threshold, setThreshold] = useState(.6);
  const [selected, setSelected] = useState<string>('');
  const rows = useMemo(() => ikigaiCareers(progress), [progress]);
  const plotted = useMemo(() => rows.map(row => ({ ...row, members: CIRCLES.filter(k => row.scores[k] !== null && row.scores[k]! >= threshold) })), [rows, threshold]);
  const positions = useMemo(() => placeInRegions(plotted), [plotted]);
  const active = plotted.find(r => r.id === selected) ?? plotted[0];
  const activeCareer = CAREERS.find(c => c.id === active?.id);
  const source = progress.country === 'US' ? 'BLS' : 'ILOSTAT';
  const employment = active?.occupation.pk;
  const wage = active?.occupation.us;

  return <div className="stack">
    <section className="workspace">
      <div className="section-heading"><div><h2>Four circles, one evidence map</h2><p>Choose a country and a threshold to see which careers enter each overlapping region.</p></div>
        <label>Country <select className="text-input" value={progress.country} onChange={e => dispatch({ type: 'country', country: e.target.value as 'US' | 'PK' })}><option value="US">United States</option><option value="PK">Pakistan</option></select></label>
      </div>
      <label htmlFor="ikigai-threshold">Circle threshold: {Math.round(threshold * 100)}%</label>
      <input id="ikigai-threshold" type="range" min="0.2" max="0.9" step="0.05" value={threshold} onChange={e => setThreshold(Number(e.target.value))} style={{ display: 'block', width: '100%', maxWidth: 390 }} />
      <p className="text-sm">A career enters a circle when its score reaches the threshold. Each dot is placed only in the region matching its actual circle membership. A missing score never counts as a pass.</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 370px), 1fr))', gap: 20, alignItems: 'start' }}>
        <div><svg viewBox="0 0 560 560" role="img" aria-label="Four overlapping Ikigai circles with career positions" style={{ width: '100%', height: 'auto' }}>
          {CIRCLES.map(k => { const [cx, cy, a, b, angle] = ELLIPSES[k]; return <ellipse key={k} cx={cx * 560} cy={cy * 560} rx={a * 560} ry={b * 560} transform={`rotate(${angle} ${cx * 560} ${cy * 560})`} fill={COLOR[k]} fillOpacity={.28} stroke={COLOR[k]} strokeWidth={2} />; })}
          <text x="385" y="55" fill={COLOR.love} fontSize="16" fontWeight="700">Love</text><text x="115" y="55" fill={COLOR.good} fontSize="16" fontWeight="700">Good at</text>
          <text x="65" y="465" fill={COLOR.needs} fontSize="16" fontWeight="700">World needs</text><text x="385" y="465" fill={COLOR.paid} fontSize="16" fontWeight="700">Paid for</text>
          {plotted.map(row => { const point = positions[row.id]; if (!point) return null; const career = CAREERS.find(c => c.id === row.id); return <g key={row.id} role="button" tabIndex={0} aria-label={`${career?.name}: ${row.members.map(k => LABEL[k]).join(', ')}`} onClick={() => setSelected(row.id)} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') setSelected(row.id); }} style={{ cursor: 'pointer' }}><circle cx={point[0] * 560} cy={point[1] * 560} r={row.id === active?.id ? 7 : 5} fill="#18222c" stroke="white" strokeWidth="2" /><title>{career?.name}</title></g>; })}
        </svg><p className="text-sm">Careers below every threshold stay in the list. Dots show membership, not distance or strength of fit.</p></div>
        <div><h3>Careers</h3>{plotted.map(row => { const career = CAREERS.find(c => c.id === row.id); const key = row.members.join('|'); return <button type="button" key={row.id} onClick={() => setSelected(row.id)} aria-pressed={active?.id === row.id} style={{ width: '100%', textAlign: 'left', display: 'flex', justifyContent: 'space-between', gap: 10, padding: '9px 4px', borderBottom: '1px solid #ddd', fontWeight: active?.id === row.id ? 700 : 400 }}><span>{career?.name}</span><span>{ZONES[key] ?? (row.members.length ? row.members.map(k => LABEL[k]).join(' + ') : 'Below threshold')} · {percent(row.overall)}</span></button>; })}</div>
      </div>
    </section>
    {active && <section className="workspace"><h2>{activeCareer?.name}: the evidence</h2><p>Matched to O*NET {active.occupation.soc}: {active.occupation.title}{activeCareer?.name !== active.occupation.title ? ' (occupation proxy)' : ''}.</p>
      <div className="career-grid">{CIRCLES.map(k => <div key={k}><div style={{ display: 'flex', justifyContent: 'space-between' }}><strong style={{ color: COLOR[k] }}>{LABEL[k]}</strong><strong>{percent(active.scores[k])}</strong></div><div className="progress-track"><div className="progress-fill" style={{ width: `${(active.scores[k] ?? 0) * 100}%`, background: COLOR[k] }} /></div></div>)}</div>
      <p className="text-sm">{progress.country === 'US' ? `US: ${wage?.annual_openings.toLocaleString()} projected annual openings, ${wage?.growth_pct}% projected growth (2025–35), $${wage?.median_annual_usd.toLocaleString()} median annual pay (2025).` : `Pakistan: ISCO-08 group ${employment?.isco2_proxy} has ${employment?.employment_thousands_2025.toLocaleString()} thousand employed (2025), versus ${employment?.employment_thousands_2021.toLocaleString()} thousand (2021); major-group median hourly earnings are PKR ${employment?.median_hourly_pkr_2025_major_group.toFixed(2)} (2025). These are broad occupation proxies, not vacancies or job-specific salary.`}</p>
      <p className="text-sm">Social impact theme: {activeCareer?.tags.includes('impact') ? 'highlighted in the hand-written career description' : 'not assessed for this career'}. This editorial tag does not affect the World needs score.</p>
      <p className="text-sm">{progress.country === 'US' ? 'Numbeo 2026 Mid-Year Cost of Living Plus Rent Index: US 54.8.' : 'Numbeo 2026 Mid-Year Cost of Living Plus Rent Index: Pakistan 12.4.'} This country context is not applied to within-country pay ranks. Social-impact labels need validated outcome data and are not scored.</p>
      <p className="text-sm">Your stated interests, grades and projects are kept as notes; they do not change a score without verified evidence. <button type="button" className="text-primary underline" onClick={() => go('interests')}>Edit interest answers</button></p>
      <label htmlFor="skills-projects">Skills, grades and projects (context only)</label><textarea id="skills-projects" className="custom-answer" maxLength={1000} value={progress.skillsAndProjects} onChange={e => dispatch({ type: 'skillsAndProjects', text: e.target.value })} />
      <p className="text-sm">Sources: <a href={EVIDENCE.sources.onet} target="_blank" rel="noreferrer" className="underline">O*NET 31.0</a> · <a href={progress.country === 'US' ? EVIDENCE.sources.bls_employment : EVIDENCE.sources.ilo_employment} target="_blank" rel="noreferrer" className="underline">{source} employment</a> · <a href={progress.country === 'US' ? EVIDENCE.sources.bls_wages : EVIDENCE.sources.ilo_earnings} target="_blank" rel="noreferrer" className="underline">{source} earnings</a> · <a href={EVIDENCE.numbeo_context.source} target="_blank" rel="noreferrer" className="underline">Numbeo cost context</a>.</p>
    </section>}
  </div>;
}
