'use client';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import * as auth from '@/lib/auth';
import type { User } from '@/lib/auth';

type Panel = 'login' | 'signup' | null;
type AuthContextValue = {
  user: User | null;
  ready: boolean;
  sessionError: string | null;
  retrySession: () => void;
  panel: Panel;
  openAuth: (mode: Exclude<Panel, null>) => void;
  closeAuth: () => void;
  signUp: (input: { name: string; email: string; password: string; character: number | null }) => Promise<void>;
  logIn: (email: string, password: string) => Promise<void>;
  adopt: (user: User) => void;
  guest: () => Promise<void>;
  logOut: () => Promise<void>;
  rename: (name: string) => void;
  deleteAccount: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [sessionAttempt, setSessionAttempt] = useState(0);
  const [panel, setPanel] = useState<Panel>(null);

  // The session cookie is checked with the API after mount.
  useEffect(() => {
    let alive = true;
    setReady(false);
    setSessionError(null);
    auth.getSessionUser().then(u => { if (alive) { setUser(u); setReady(true); } })
      .catch(error => { if (alive) { setSessionError(error instanceof Error ? error.message : 'Could not reach the server.'); setReady(true); } });
    return () => { alive = false; };
  }, [sessionAttempt]);

  const signUp = useCallback<AuthContextValue['signUp']>(async input => { await auth.signUp(input); }, []);
  const logIn = useCallback<AuthContextValue['logIn']>(async (email, password) => {
    setUser(await auth.logIn(email, password));
    setPanel(null);
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    user, ready, panel, sessionError, retrySession: () => setSessionAttempt(n => n + 1),
    openAuth: mode => setPanel(mode),
    closeAuth: () => setPanel(null),
    signUp, logIn,
    adopt: u => { setUser(u); setPanel(null); },
    guest: async () => { setUser(await auth.continueAsGuest()); setPanel(null); },
    logOut: async () => { await auth.logOut(); setUser(null); setPanel(null); },
    rename: async name => { if (user && !user.guest) { try { setUser(await auth.updateName(name)); } catch { /* keep old name */ } } },
    deleteAccount: async () => { if (user) { await auth.deleteAccount(); setUser(null); setPanel(null); } },
  }), [user, ready, panel, sessionError, signUp, logIn]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
