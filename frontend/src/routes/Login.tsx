import { FormEvent, useState } from "react";

interface LoginProps {
  onSuccess: () => void;
  login: (email: string, password: string) => Promise<void>;
}

export function Login({ onSuccess, login }: LoginProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-6 py-12">
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--accent)] text-sm font-bold text-white">
          Tg
        </span>
        <div>
          <p className="text-lg font-semibold tracking-tight">Tagado</p>
          <p className="text-xs text-slate-500">Follow-ups that stay live</p>
        </div>
      </div>
      <h1 className="mt-8 text-3xl font-semibold tracking-tight">Sign in</h1>
      <p className="mt-2 text-sm text-slate-600">
        See who owes you money, approve follow-ups, and confirm payments in one place.
      </p>
      <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
        <label className="block text-sm font-medium">
          Email
          <input
            className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2.5 outline-none focus:border-[var(--accent)]"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>
        <label className="block text-sm font-medium">
          Password
          <input
            className="mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2.5 outline-none focus:border-[var(--accent)]"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>
        {error ? <p className="text-sm text-rose-700">{error}</p> : null}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-[var(--ink)] px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p className="mt-5 text-xs leading-relaxed text-slate-500">
        Reviewing Tagado? Use the test login from the submission notes.
      </p>
    </main>
  );
}
