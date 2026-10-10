import { api } from '@/lib/api';
import { summary } from '@/lib/dna';
import type { Progress } from '@/lib/types';

export type RagSource = { n: number; title: string; excerpt: string };
export type RagAnswer = { status: 'ok' | 'not_configured' | 'no_match' | 'unavailable'; answer: string | null; sources: RagSource[] };

/** Ask Yuki a question grounded in the Learning DNA questionnaire, its scoring rules and its references. */
export const askYuki = (question: string, progress: Progress) => api<RagAnswer>('/rag/ask', {
  method: 'POST', body: { question, profile: summary(progress.dna), progress },
});
