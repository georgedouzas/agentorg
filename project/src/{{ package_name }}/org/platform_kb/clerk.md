# Clerk

Drop-in auth used to add SSO (email + social) to the dashboard. No CLI — everything is configured at clerk.com.

## Setup

1. Create a Clerk account at [clerk.com](https://clerk.com).
2. New Application → name it after the org.
3. From **API Keys**, copy:
   - `Publishable key` → `CLERK_PUBLISHABLE_KEY` in `.env` (and on Vercel).
   - `Secret key` → `CLERK_SECRET_KEY` (server-side, set on Railway only).
4. Add allowed origins under **Domains**: localhost:5173 (dev) + the Vercel URL (prod).

## Behavior

- When `CLERK_PUBLISHABLE_KEY` is unset, the dashboard falls back to a per-browser UUID stored in localStorage (no real auth).
- The frontend's `useIdentity` hook handles both flows transparently.

## Pitfalls

- Free tier limits: 10K MAU. Plan accordingly.
- Publishable key is safe to commit (designed for client use). Secret key is **not** — keep it server-side.
- Domain mismatch is the #1 cause of "auth not working" — check **Domains** carefully.
