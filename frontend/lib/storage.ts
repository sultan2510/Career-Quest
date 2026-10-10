import { api } from '@/lib/api';
import { emptyProgress, type Progress } from '@/lib/types';

const PREFIX = 'careerquest:';

function read<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(PREFIX + key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch { return fallback; }
}
function write(key: string, value: unknown) {
  try { window.localStorage.setItem(PREFIX + key, JSON.stringify(value)); return true; } catch { return false; }
}
function remove(key: string) {
  try { window.localStorage.removeItem(PREFIX + key); } catch { /* ignore */ }
}
export const store = { read, write, remove };

const merge = (saved: Partial<Progress> | null): Progress => ({
  ...emptyProgress(),
  ...(saved && saved.v === 1 ? saved : {}),
  interests: saved?.interests ?? {},
  simulationDrafts: saved?.simulationDrafts ?? {},
  mentorMessages: saved?.mentorMessages ?? [],
});

// Read-only migration helpers for progress saved by older browser-only guest mode.
export const loadLocal = (id: string) => merge(read<Partial<Progress> | null>(`progress:${id}`, null));
export const hasLocal = (id: string) => read<unknown>(`progress:${id}`, null) !== null;
export const clearLocal = (id: string) => remove(`progress:${id}`);

/** Account and guest progress live on the server. Never replace saved data after a failed load. */
export async function loadProgress(_userId: string): Promise<Progress> {
  return merge(await api<Partial<Progress>>('/progress'));
}

export async function saveProgress(_userId: string, progress: Progress) {
  await api('/progress', { method: 'PUT', body: progress });
}
