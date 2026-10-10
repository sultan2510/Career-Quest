'use client';
import { Sprout } from 'lucide-react';
import { AuthProvider, useAuth } from '@/components/providers/auth-provider';
import { ProgressProvider } from '@/components/providers/progress-provider';
import { useProgress } from '@/components/providers/progress-provider';
import { AuthScreen } from '@/components/auth/auth-screen';
import { AppShell } from '@/components/quest/app-shell';
import { Button } from '@/components/ui/button';

function AccountPanel() {
  const { loaded, loadError, retryLoad, retrySave } = useProgress();
  if (!loaded) return <div className="splash" role="status"><div>{loadError ? <><p>{loadError}</p><Button onClick={retryLoad}>Try again</Button></> : 'Loading your saved progress…'}</div></div>;
  return <AuthScreen beforeSignUp={retrySave} />;
}

function Gate() {
  const { user, ready, panel, sessionError, retrySession } = useAuth();
  if (!ready) return <div className="splash" role="status"><div><Sprout size={32} />Loading your quest…</div></div>;
  if (sessionError) return <div className="splash" role="alert"><div><p>Could not load your session: {sessionError}</p><Button onClick={retrySession}>Try again</Button></div></div>;
  if (!user) return <AuthScreen key="auth" />;
  return <ProgressProvider key={user.id} userId={user.id}>{panel ? <AccountPanel /> : <AppShell />}</ProgressProvider>;
}

export default function Root() {
  return <AuthProvider><Gate /></AuthProvider>;
}
