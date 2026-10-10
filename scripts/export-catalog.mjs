/** Export the real UI's data for Python retrieval; Node 22.18+ supports TS stripping. */
import { readFile, writeFile } from 'node:fs/promises';
import { stripTypeScriptTypes } from 'node:module';
import { runInNewContext } from 'node:vm';
import { CAREERS } from '../frontend/lib/data/careers.ts';
import { DNA_SCENARIOS, REFERENCES } from '../frontend/lib/data/dna.ts';

const source = await readFile(new URL('../frontend/lib/dna.ts', import.meta.url), 'utf8');
const definition = source.match(/export const DIMS:[\s\S]*?\n};/);
if (!definition) throw new Error('Could not find the questionnaire dimension definitions.');
const code = stripTypeScriptTypes(definition[0]).replace('export const', 'const');
const dimensions = runInNewContext(`${code}\nDIMS`, {}, { timeout: 1000 });
const catalog = { careers: CAREERS, dna_scenarios: DNA_SCENARIOS, dna_dimensions: dimensions, references: REFERENCES };
const destination = new URL('../backend/catalog.json', import.meta.url);
const output = JSON.stringify(catalog, null, 2) + '\n';
if (process.argv.includes('--check')) {
  if (await readFile(destination, 'utf8') !== output) throw new Error('Catalog is stale. Run node scripts/export-catalog.mjs.');
  console.log('Retrieval catalog matches the UI.');
} else {
  await writeFile(destination, output);
  console.log(`Exported ${CAREERS.length} careers and ${DNA_SCENARIOS.length} scenarios.`);
}
