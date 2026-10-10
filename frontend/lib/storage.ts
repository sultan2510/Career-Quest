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

const merge = (saved: Partial<Progress> | null): Progress => ({ ...emptyProgress(), ...(saved && saved.v === 1 ? saved : {}), interests: saved?.interests ?? {} });

// Guest progress lives in this browser only.
export const loadLocal = (id: string) => merge(read<Partial<Progress> | null>(`progress:${id}`, null));
export const hasLocal = (id: string) => read<unknown>(`progress:${id}`, null) !== null;
export const clearLocal = (id: string) => remove(`progress:${id}`);

/** Signed-in progress lives on the server. Throws if it can't be loaded, so an empty copy never overwrites saved data. */
export async function loadProgress(userId: string): Promise<Progress> {
  if (userId === 'guest') return loadLocal(userId);
  return merge(await api<Partial<Progress>>('/progress'));
}

export async function saveProgress(userId: string, progress: Progress) {
  if (userId === 'guest') {
    if (!write(`progress:${userId}`, progress)) throw new Error('Browser could not save your progress.');
    return;
  }
  await api('/progress', { method: 'PUT', body: progress });
}
