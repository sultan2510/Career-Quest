// Exercise the actual TypeScript geometry without adding a test-runner dependency.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('../frontend/node_modules/typescript');
const file = path.join(__dirname, '../frontend/lib/venn.ts');
const js = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const moduleUnderTest = { exports: {} };
new Function('require', 'module', 'exports', js)(
  () => ({ CIRCLES: ['love', 'good', 'needs', 'paid'] }), moduleUnderTest, moduleUnderTest.exports,
);
const { membership, regionPoints, placeInRegions, regionKey } = moduleUnderTest.exports;
const regions = regionPoints();
assert.equal(Object.keys(regions).length, 15, 'all nonempty four-set regions must exist');
const items = Object.entries(regions).map(([key]) => ({ id: key, members: key.split('|') }));
const placed = placeInRegions(items);
for (const item of items) {
  assert.ok(placed[item.id], `missing position for ${item.id}`);
  assert.equal(regionKey(membership(...placed[item.id])), item.id, `incorrect membership for ${item.id}`);
}
console.log('Validated all 15 Venn regions and exact dot membership');
