'use client';
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from 'react';
import { AccountFlow, type Mode } from '@/components/auth/account-flow';
import { AlertCircle, ArrowLeft, ArrowRight, Eye, EyeOff, Sprout, TriangleAlert } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/components/providers/auth-provider';
import { CHARACTERS } from '@/lib/data/characters';
import { AuthError, emailProblem, nameProblem, passwordProblem, passwordStrength, validateSignUp } from '@/lib/auth';

// Every line here is a fact about this prototype, not a marketing claim.
const TAGLINES = [
  'Seven short stories. About fifteen decisions. No right answers.',
  'Follow-ups adapt to what you chose, so no two runs look alike.',
  'Try a day in a career before you commit to one.',
  'Guest progress is saved privately. An account follows you across devices.',
];

function Taglines() {
  const [i, setI] = useState(0);
  useEffect(() => {
    // Motion-averse visitors get one line instead of a carousel.
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const t = setInterval(() => setI(n => (n + 1) % TAGLINES.length), 5000);
    return () => clearInterval(t);
  }, []);
  return <div className="auth-tagline"><p key={i}>{TAGLINES[i]}</p></div>;
}

const FieldError = ({ id, children }: { id: string; children: ReactNode }) =>
  <span className="field-error" id={id}><AlertCircle />{children}</span>;

export function AuthScreen({ beforeSignUp }: { beforeSignUp?: () => Promise<void> } = {}) {
  const { user, panel, signUp, logIn, guest, closeAuth, adopt } = useAuth();
  const [mode, setMode] = useState<Mode>(() => {
    const q = new URLSearchParams(window.location.search);
    return q.get('verify') ? 'verify' : q.get('reset') ? 'reset' : panel ?? 'login';
  });
  const [token] = useState(() => { const q = new URLSearchParams(window.location.search); return q.get('verify') ?? q.get('reset') ?? ''; });
  const [pending, setPending] = useState('');
  const [step, setStep] = useState<1 | 2>(1);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
  const [character, setCharacter] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [touched, setTouched] = useState<{ name?: boolean; email?: boolean; password?: boolean }>({});
  const [attempted, setAttempted] = useState(false);
  const [capsOn, setCapsOn] = useState(false);
  const nameRef = useRef<HTMLInputElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  const signingUp = mode === 'signup';
  // A field speaks up once you've left it, or once you've tried to submit.
  const seen = (k: 'name' | 'email' | 'password') => attempted || !!touched[k];
  const nameErr = signingUp ? nameProblem(name) : null;
  const emailErr = email.trim() === '' ? 'Enter your email address.' : emailProblem(email);
  const pwErr = signingUp ? passwordProblem(password) : password ? null : 'Enter your password.';
  const strength = passwordStrength(password);
  // Signup leans on the strength meter for live feedback, so its message waits for a submit.
  const pwErrShown = signingUp ? attempted && !!pwErr : seen('password') && !!pwErr;

  const switchMode = (next: 'login' | 'signup') => {
    setMode(next); setStep(1); setError(''); setTouched({}); setAttempted(false); setCapsOn(false);
  };

  // Send the caret to the first thing that needs fixing, rather than just printing a banner.
  const focusFirstInvalid = () => {
    if (signingUp && nameProblem(name)) return nameRef.current?.focus();
    if (emailProblem(email) || email.trim() === '') return emailRef.current?.focus();
    passwordRef.current?.focus();
  };

  const capsCheck = (e: KeyboardEvent<HTMLInputElement>) => {
    if (typeof e.getModifierState === 'function') setCapsOn(e.getModifierState('CapsLock'));
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setAttempted(true);
    if (mode === 'signup' && step === 1) {
      if (validateSignUp(name, email, password)) return focusFirstInvalid();
      return setStep(2);
    }
    if (nameErr || emailErr || pwErr) return focusFirstInvalid();
    setBusy(true);
    try {
      if (mode === 'login') await logIn(email, password);
      else { if (beforeSignUp) await beforeSignUp(); await signUp({ name, email, password, character }); setPending(email.trim().toLowerCase()); setMode('verify'); setBusy(false); }
    } catch (err) {
      if (err instanceof AuthError && err.code === 'email_not_verified') { setPending(email.trim().toLowerCase()); setMode('verify'); setBusy(false); return; }
      setError(err instanceof AuthError ? err.message : 'Something went wrong. Please try again.');
      setBusy(false);
    }
  };

  const enterGuest = async () => {
    setError(''); setBusy(true);
    try { await guest(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not start guest mode. Please try again.'); }
    finally { setBusy(false); }
  };

  return (
    <div className="auth-shell">
      <div className="auth-bg" aria-hidden="true" />
      <div className="auth-inner">
        <div className="auth-brand">
          <div className="logo"><div className="logo-mark"><Sprout size={22} /></div><div>Career<span className="accent">Quest</span></div></div>
        </div>
        <Taglines />
        <main className="auth-card">
          {user && <Button variant="ghost" size="sm" className="mb-4 -ml-3" onClick={closeAuth}><ArrowLeft />Back to my quest</Button>}
          {mode === 'verify' || mode === 'forgot' || mode === 'reset' ? <AccountFlow mode={mode} email={pending || email} token={token} setMode={setMode} adopt={adopt} /> : mode === 'signup' && step === 2 ? (
            <form onSubmit={submit}>
              <h1>Pick your character</h1>
              <p>Choose the one that feels most like you today. It’s a starting point, not a label.</p>
              <div className="picker" role="group" aria-label="Characters">
                {CHARACTERS.map((c, i) => (
                  <button type="button" key={c.id} aria-pressed={character === i} onClick={() => setCharacter(i)}>
                    <div className="art"><img src={c.image} alt="" /></div><strong>{c.name}</strong><small>{c.tag}</small>
                  </button>
                ))}
              </div>
              {error && <div className="form-error" role="alert">{error}</div>}
              <Button type="submit" className="w-full h-11" disabled={busy}>{busy ? 'Creating your account…' : 'Start my quest'} <ArrowRight /></Button>
              <Button type="button" variant="ghost" className="w-full mt-2" onClick={() => setStep(1)}>Back</Button>
            </form>
          ) : (
            <form onSubmit={submit} noValidate>
              <h1>{mode === 'login' ? 'Welcome back' : 'Start your quest'}</h1>
              <p>{mode === 'login' ? 'Pick up where you left off.' : 'Create an account to save your progress.'}</p>
              <div className="tabs" role="tablist" aria-label="Account">
                <button type="button" role="tab" aria-selected={mode === 'login'} onClick={() => switchMode('login')}>Log in</button>
                <button type="button" role="tab" aria-selected={mode === 'signup'} onClick={() => switchMode('signup')}>Sign up</button>
              </div>
              {signingUp && <div className="field">
                <label htmlFor="name">Your name</label>
                <input id="name" ref={nameRef} className="text-input" autoComplete="given-name" value={name}
                  aria-invalid={seen('name') && !!nameErr} aria-describedby={seen('name') && nameErr ? 'name-error' : undefined}
                  onChange={e => setName(e.target.value)} onBlur={() => setTouched(t => ({ ...t, name: true }))} />
                {seen('name') && nameErr && <FieldError id="name-error">{nameErr}</FieldError>}
              </div>}
              <div className="field">
                <label htmlFor="email">Email</label>
                <input id="email" ref={emailRef} type="email" className="text-input" autoComplete="email" value={email}
                  aria-invalid={seen('email') && !!emailErr} aria-describedby={seen('email') && emailErr ? 'email-error' : undefined}
                  onChange={e => setEmail(e.target.value)} onBlur={() => setTouched(t => ({ ...t, email: true }))} />
                {seen('email') && emailErr && <FieldError id="email-error">{emailErr}</FieldError>}
              </div>
              <div className="field">
                <label htmlFor="password">Password</label>
                <div className="pw-wrap">
                  <input id="password" ref={passwordRef} type={show ? 'text' : 'password'} className="text-input"
                    autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={password}
                    aria-invalid={pwErrShown} aria-describedby={pwErrShown ? 'password-error' : undefined}
                    onChange={e => setPassword(e.target.value)}
                    onBlur={() => { setTouched(t => ({ ...t, password: true })); setCapsOn(false); }}
                    onKeyDown={capsCheck} onKeyUp={capsCheck} />
                  <button type="button" className="pw-toggle" aria-label={show ? 'Hide password' : 'Show password'} onClick={() => setShow(!show)}>{show ? <EyeOff size={18} /> : <Eye size={18} />}</button>
                </div>
                {signingUp && password && <div className="strength">
                  <span className={`strength-track s${strength.score}`} aria-hidden="true"><i /><i /><i /></span>
                  <span className="strength-label">{strength.label}</span>
                </div>}
                {capsOn && <span className="caps-warn"><TriangleAlert />Caps Lock is on.</span>}
                {pwErrShown && pwErr && <FieldError id="password-error">{pwErr}</FieldError>}
                {signingUp && !password && <span className="hint">At least 8 characters.</span>}
                {mode === 'login' && <button type="button" className="hint underline" onClick={() => { setError(''); setMode('forgot'); }}>Forgot password?</button>}
              </div>
              {error && <div className="form-error" role="alert">{error}</div>}
              <Button type="submit" className="w-full h-11" disabled={busy}>{busy ? 'Logging in…' : mode === 'login' ? 'Log in' : 'Next: choose a character'} <ArrowRight /></Button>
              {!user && <><div className="divider">or</div><Button type="button" variant="outline" className="w-full h-11" disabled={busy} onClick={() => void enterGuest()}>{busy ? 'Starting guest session…' : 'Explore as a guest'}</Button></>}
              <p className="text-xs mt-4" style={{ color: 'var(--muted-foreground)' }}>Guest work is saved in the database under a private browser cookie for 90 days. Create an account to use it on other devices.</p>
            </form>
          )}
        </main>
      </div>
    </div>
  );
}
