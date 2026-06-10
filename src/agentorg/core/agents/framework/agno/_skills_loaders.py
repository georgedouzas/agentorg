"""Custom `agno.skills.SkillLoader` subclasses for non-local skill sources."""

import hashlib
import subprocess
from pathlib import Path

from agno.skills.loaders.base import SkillLoader
from agno.skills.loaders.local import LocalSkills
from agno.skills.skill import Skill

CACHE_ROOT = Path.home() / '.cache' / 'agentorg' / 'skills'


class GitHubSkills(SkillLoader):
    """Skill loader that shallow-clones a public GitHub repo on demand and caches it on disk.

    Arguments:
        url: The repository URL to clone.
        ref: The branch, tag, or commit ref to clone.
        subpath: A directory inside the repo that holds the SKILL.md folders.
        validate: When True, validate each loaded skill against the SKILL.md spec.
    """

    def __init__(self, url: str, ref: str = 'HEAD', subpath: str = '', *, validate: bool = True) -> None:
        self.url = url
        self.ref = ref
        self.subpath = subpath
        self.validate = validate

    def load(self) -> list[Skill]:
        """Clone the repo if needed and load the SKILL.md folders it contains.

        Returns:
            skills: The discovered `agno.Skill` instances.
        """
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
