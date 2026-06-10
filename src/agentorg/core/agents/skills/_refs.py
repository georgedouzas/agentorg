"""Skills references."""

DEFAULT_SKILLS_REFS: dict[str, dict[str, str | bool]] = {
    'superpowers': {
        'url': 'https://github.com/obra/superpowers',
        'ref': 'main',
        'subpath': 'skills',
        'validate': True,
    },
    'context7': {
        'url': 'https://github.com/upstash/context7',
        'ref': 'master',
        'subpath': 'skills',
        'validate': True,
    },
    'awesome-copilot': {
        'url': 'https://github.com/github/awesome-copilot',
        'ref': 'main',
        'subpath': 'skills',
        'validate': False,
    },
}
