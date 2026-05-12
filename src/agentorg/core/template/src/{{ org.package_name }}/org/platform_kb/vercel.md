# Vercel

Static + edge platform used to host the React frontend (Vite build).

## Auth & CLI

- Install [`vercel`](https://vercel.com/docs/cli) and run `vercel login`.
- `vercel.json` at the repo root pins the build command (`nox -s build -- frontend`) and output dir.

## Common tasks

```sh
vercel             # link the local repo to a Vercel project (first time)
vercel --prod      # production deploy
vercel env add     # add an env var (interactive)
vercel logs <url>  # tail recent logs
```

## Required env vars

- `API_BASE_URL` — full Railway URL of the API. Without this, the SPA can't talk cross-origin in production.
- `CLERK_PUBLISHABLE_KEY` — only if using Clerk SSO.

## Pitfalls

- Vercel runs `npm install` in `src/frontend/` — make sure `package-lock.json` is committed.
- Preview deploys for PRs need the same env vars as production, otherwise they 500 silently.
- Build output dir is `public/` (not the default `dist/`); `vercel.json` sets this.
