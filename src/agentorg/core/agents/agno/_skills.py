"""Custom `agno.skills.SkillLoader` subclasses for non-local skill sources."""

import hashlib
import subprocess
from pathlib import Path

from agno.skills.loaders.base import SkillLoader
from agno.skills.loaders.local import LocalSkills
from agno.skills.skill import Skill

CACHE_ROOT = Path.home() / '.cache' / 'agentorg' / 'skills'
DEFAULT_SKILLS_REFS: dict[str, dict[str, str]] = {
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


class GitHubSkills(SkillLoader):
    """Loads skills from a (public) GitHub repo via shallow clone, cached on disk by (url, ref)."""

    def __init__(self, url: str, ref: str = 'HEAD', subpath: str = '', *, validate: bool = True) -> None:
        self.url = url
        self.ref = ref
        self.subpath = subpath
        self.validate = validate

    def load(self) -> list[Skill]:
        target = self._ensure_clone() / self.subpath if self.subpath else self._ensure_clone()
        return LocalSkills(str(target), validate=self.validate).load()

    def _ensure_clone(self) -> Path:
        key = hashlib.sha1(f'{self.url}@{self.ref}'.encode(), usedforsecurity=False).hexdigest()[:12]
        dest = CACHE_ROOT / key
        if dest.exists():
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(  # noqa: S603
            ['git', 'clone', '--depth', '1', '--branch', self.ref, self.url, str(dest)],  # noqa: S607
            check=True,
            capture_output=True,
        )
        return dest
