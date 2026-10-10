import { REFERENCES } from '@/lib/data/dna';

/** Shown at the bottom of every section, collapsed. Scenario sources in the Learning DNA view link here by number. */
export function References() {
  return <details className="sensei-panel references" id="references" style={{ marginTop: 28 }}>
    <summary>References ({REFERENCES.length})</summary>
    <ol style={{ margin: '12px 0 0', paddingLeft: 22, display: 'grid', gap: 8, fontSize: 13, lineHeight: 1.5 }}>
      {REFERENCES.map(r => <li key={r.id} id={`ref-${r.id}`} style={{ overflowWrap: 'anywhere' }}>
        {r.url ? <>{r.text.replace(r.url, '').trim()} <a href={r.url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'underline' }}>{r.url.replace('https://', '')}</a></> : r.text}
      </li>)}
    </ol>
  </details>;
}
