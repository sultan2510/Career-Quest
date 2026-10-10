export const RIASEC = ['Realistic', 'Investigative', 'Artistic', 'Social', 'Enterprising', 'Conventional'] as const;
export type Riasec = (typeof RIASEC)[number];

// Original short screening questions inspired by Holland's RIASEC work activities.
// This 18-item set is not the validated O*NET Interest Profiler.
export const INTEREST_ITEMS: { id: string; kind: Riasec; text: string }[] = [
  { id: 'R1', kind: 'Realistic', text: 'Fix, build, or assemble equipment or structures' },
  { id: 'R2', kind: 'Realistic', text: 'Use tools, vehicles, or electronics in practical work' },
  { id: 'R3', kind: 'Realistic', text: 'Work outdoors or in a workshop' },
  { id: 'I1', kind: 'Investigative', text: 'Run experiments or analyse data to answer a question' },
  { id: 'I2', kind: 'Investigative', text: 'Solve complex logic, maths, or technical problems' },
  { id: 'I3', kind: 'Investigative', text: 'Investigate scientific or technical discoveries' },
  { id: 'A1', kind: 'Artistic', text: 'Create music, art, design, writing, or performance' },
  { id: 'A2', kind: 'Artistic', text: 'Imagine original ideas with few fixed rules' },
  { id: 'A3', kind: 'Artistic', text: 'Design how something looks, sounds, or feels' },
  { id: 'S1', kind: 'Social', text: 'Teach, coach, or train other people' },
  { id: 'S2', kind: 'Social', text: 'Listen to and help people with their problems' },
  { id: 'S3', kind: 'Social', text: 'Work with a team whose goal is helping others' },
  { id: 'E1', kind: 'Enterprising', text: 'Lead a group and persuade people to back a plan' },
  { id: 'E2', kind: 'Enterprising', text: 'Start or grow a business or project' },
  { id: 'E3', kind: 'Enterprising', text: 'Negotiate, sell, or pitch ideas' },
  { id: 'C1', kind: 'Conventional', text: 'Keep records and data accurate and organised' },
  { id: 'C2', kind: 'Conventional', text: 'Follow clear procedures to process numbers or documents' },
  { id: 'C3', kind: 'Conventional', text: 'Work with budgets, schedules, or spreadsheets' },
];

export function interestScores(responses: Record<string, number>): Partial<Record<Riasec, number>> {
  const out: Partial<Record<Riasec, number>> = {};
  for (const kind of RIASEC) {
    const items = INTEREST_ITEMS.filter(item => item.kind === kind);
    if (items.every(item => responses[item.id] >= 1 && responses[item.id] <= 5)) {
      out[kind] = items.reduce((sum, item) => sum + (responses[item.id] - 1) / 4, 0) / items.length;
    }
  }
  return out;
}
