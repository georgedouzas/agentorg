# GitHub

Source-of-truth for the org's code and the entry point for most CI/CD integrations.

## Auth & CLI

- Install the [`gh` CLI](https://cli.github.com/) and run `gh auth login`.
- Personal access tokens are needed for CI: settings → developer settings → tokens.

## Common tasks

```sh
gh repo create <owner>/<slug> --public --source=. --push     # create + push
gh repo set-default <owner>/<slug>                           # bind a default repo
gh secret set NAME --body "value"                            # set repo secret (CI)
gh pr create --title "..." --body "..."                      # open PR
```

## Pitfalls

- New repos default to `main`. If a workflow references `master`, it won't run.
- Secrets aren't echoed back; once set, they can only be replaced.
- Rate limits apply to unauthenticated calls — always auth.
