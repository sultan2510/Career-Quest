import type { DnaState } from '@/lib/dna-types';

export const TRAITS = ['creative', 'analytical', 'social', 'independent', 'adventurous', 'purposeful'] as const;
export type Trait = (typeof TRAITS)[number];

export const TRAIT_LABELS: Record<Trait, string> = {
  creative: 'Creativity',
  analytical: 'Analysis',
  social: 'Teamwork',
  independent: 'Autonomy',
  adventurous: 'Exploration',
  purposeful: 'Purpose',
};

export type Tone = 'coral' | 'mint' | 'yellow' | 'lilac';
export type Quality = 0 | 1 | 2;
export type IconKey = 'design' | 'data' | 'environment' | 'software' | 'education' | 'health' | 'product' | 'journalism';

export type Character = {
  id: string;
  name: string;
  initials: string;
  tag: string;
  description: string;
  traits: string[];
  tone: Tone;
  image: string;
  seed: Partial<Record<Trait, number>>;
};

export type Choice = { text: string; outcome: string; quality: Quality };
export type Scene = { time: string; title: string; prompt: string; choices: Choice[] };

export type Career = {
  id: string;
  name: string;
  category: string;
  icon: IconKey;
  tone: Tone;
  description: string;
  tasks: string[];
  reality: string;
  aiNote: string;
  profile: Partial<Record<Trait, number>>;
  tags: string[];
  skill: string;
  project: string;
  onet: string;
  scenes: [Scene, Scene];
};

export type Decision = {
  scene: number;
  text: string;
  outcome: string;
  /** null = not scored (free-text answers) */
  quality: Quality | null;
  source: 'choice' | 'free-text';
};

export interface SimulationDecision {
  scene_id: string;
  user_choice: string;
  free_text_explanation?: string;
  enjoyment_rating?: number;
  confidence_rating?: number;
  timestamp: string;
}

export type LoggedDecision = SimulationDecision & Pick<Decision, 'outcome' | 'quality' | 'source'>;

export type SimulationDraft = {
  run_id: string;
  career_id: string;
  current_scene_id: string;
  decision_log: LoggedDecision[];
  started_at: string;
};

export type Evidence = {
  id: string;
  careerId: string;
  enjoyment: number;
  confidence: number;
  decisions: Decision[];
  decision_log?: LoggedDecision[];
  at: string;
};

export type JournalEntry = { id: string; at: string; prompt: string; text: string };

export type MentorMessage = {
  id: string;
  at: string;
  role: 'you' | 'yuki';
  text: string;
  sources?: { n: number; title: string; excerpt: string }[];
};

export type Progress = {
  v: 1;
  character: number | null;
  evidence: Evidence[];
  simulationDrafts: Record<string, SimulationDraft>;
  tasks: Record<string, string[]>;
  journal: JournalEntry[];
  mentorMessages: MentorMessage[];
  planCareer: string | null;
  explored: string[];
  dna: DnaState;
  interests: Record<string, number>;
  country: 'US' | 'PK';
  statedInterests: string;
  skillsAndProjects: string;
};

export const emptyProgress = (): Progress => ({
  v: 1,
  character: null,
  evidence: [],
  simulationDrafts: {},
  tasks: {},
  journal: [],
  mentorMessages: [],
  planCareer: null,
  explored: [],
  dna: { answers: {}, tie: null, recon: null },
  interests: {},
  country: 'US',
  statedInterests: '',
  skillsAndProjects: '',
});
