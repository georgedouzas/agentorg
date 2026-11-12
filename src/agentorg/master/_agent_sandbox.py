"""Run a drafted agent on real prompts in a preview runtime and report what it did."""

import tempfile
from collections.abc import Iterable
from pathlib import Path

from claude_agent_sdk import ClaudeSDKClient

from ..core.operations import ClientFactory, OrgRuntime
from ..core.spec import Spec
from ._models import CustomSkill


def _report(index: int, prompt: str, result: dict[str, object], tools: list[str], cost: float) -> str:
    """Return the Markdown report of one sandbox prompt."""
    lines = [f'### Prompt {index}', f'> {prompt}', '', f"**Status:** {result['status']} · **Cost:** {cost:.4f} USD"]
    lines.append(f"**Tools called:** {', '.join(tools) if tools else 'none'}")
    lines += ['', str(result.get('output') or '(no output)')]
    return '\n'.join(lines)


async def sandbox_run(
    spec: Spec,
    agent_id: str,
    prompts: list[str],
    custom_skills: Iterable[CustomSkill] = (),
    client_factory: ClientFactory = ClaudeSDKClient,
) -> str:
    """Run `agent_id` once per prompt on the Claude agent harness in preview mode and report each run.

    Arguments:
        spec: The working spec, whose structure must be complete.
        agent_id: The agent to run.
        prompts: The prompts to run in order.
        custom_skills: The interview's custom skills, written where the agent can load them.
        client_factory: Opens an SDK client for given options.

    Returns:
        report: Markdown with each prompt's status, cost, tool calls and output.
    """
    with tempfile.TemporaryDirectory(prefix='agentorg-sandbox-') as tmp:
        root = Path(tmp)
        for skill in custom_skills:
            (root / 'skills' / skill.name).mkdir(parents=True)
            (root / 'skills' / skill.name / 'SKILL.md').write_text(skill.skill_md)
        environ = {'AGENTORG_PREVIEW_MODE': 'true'}
        runtime = OrgRuntime(
            spec,
            environ=environ,
            data_dir=root,
            skills_dir=root / 'skills',
            client_factory=client_factory,
        )
        await runtime.start()
        sections = []
        try:
            for index, prompt in enumerate(prompts, start=1):
                result = await runtime.run_target(agent_id, prompt, None, 'sandbox')
                run = await runtime.store.get_run(str(result['run_id'])) if 'run_id' in result else None
                tools = [str(e['name']) for e in (run.transcript if run else []) if e.get('type') == 'tool_call']
                sections.append(_report(index, prompt, result, tools, run.cost_usd if run else 0.0))
        finally:
            await runtime.stop()
    return '\n\n'.join(sections)
