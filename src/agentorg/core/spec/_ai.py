"""The org's agents and the unit tree that organises them."""

from collections import Counter

from pydantic import model_validator

from ._agents import Agent, Unit
from ._config import SpecModel

MAX_DEPTH = 6


class AI(SpecModel):
    """The org's agent definitions and its root unit."""

    agents: list[Agent]
    root: Unit

    def _validate_ids(self) -> None:
        ids = [agent.id for agent in self.agents] + [unit.id for unit in self.root.iter_units()]
        duplicates = sorted(id_ for id_, count in Counter(ids).items() if count > 1)
        if duplicates:
            msg = f'Agent and unit ids must be unique; duplicated: {duplicates}.'
            raise ValueError(msg)

    def _validate_membership(self) -> None:
        agent_ids = {agent.id for agent in self.agents}
        placed: list[str] = []
        for unit in self.root.iter_units():
            placed.extend(member for member in unit.member_refs if isinstance(member, str))
            placed.extend([unit.lead] if unit.lead else [])
        unknown = sorted(set(placed) - agent_ids)
        if unknown:
            msg = f'Units reference undeclared agents: {unknown}.'
            raise ValueError(msg)
        counts = Counter(placed)
        misplaced = sorted(id_ for id_ in agent_ids if counts[id_] != 1)
        if misplaced:
            msg = f'Each agent must be a member or lead of exactly one unit; check: {misplaced}.'
            raise ValueError(msg)

    def _validate_referrals(self) -> None:
        targets = {agent.id for agent in self.agents} | {unit.id for unit in self.root.iter_units()}
        for agent in self.agents:
            unknown = [referral.refer_to for referral in agent.persona.out_of_scope if referral.refer_to not in targets]
            if unknown:
                msg = f"Agent '{agent.id}' refers out-of-scope topics to undeclared agents or units: {unknown}."
                raise ValueError(msg)

    def _validate_councils(self) -> None:
        agents = {agent.id: agent for agent in self.agents}
        for unit in self.root.iter_units():
            if unit.model != 'council' or unit.decision != 'majority':
                continue
            for member in unit.member_refs:
                schema = agents[member].output.json_schema if isinstance(member, str) else None
                if not schema or 'choice' not in schema.get('properties', {}):
                    msg = f"Majority council '{unit.id}': members must be agents with a json `choice` output."
                    raise ValueError(msg)

    def _validate_budgets(self, unit: Unit, ceiling: float | None) -> None:
        if unit.monthly_usd is not None and ceiling is not None and unit.monthly_usd > ceiling:
            msg = f"Unit '{unit.id}' has monthly_usd {unit.monthly_usd}, above its parent's {ceiling}."
            raise ValueError(msg)
        for member in unit.member_refs:
            if isinstance(member, Unit):
                self._validate_budgets(member, unit.monthly_usd if unit.monthly_usd is not None else ceiling)

    @model_validator(mode='after')
    def _validate_tree(self) -> 'AI':
        if self.root.depth() > MAX_DEPTH:
            msg = f'The unit tree is {self.root.depth()} levels deep; the maximum is {MAX_DEPTH}.'
            raise ValueError(msg)
        self._validate_ids()
        self._validate_membership()
        self._validate_referrals()
        self._validate_councils()
        self._validate_budgets(self.root, None)
        return self

    def agent(self, agent_id: str) -> Agent:
        """Return the agent with id `agent_id`."""
        return next(agent for agent in self.agents if agent.id == agent_id)

    def unit(self, unit_id: str) -> Unit:
        """Return the unit with id `unit_id`."""
        return next(unit for unit in self.root.iter_units() if unit.id == unit_id)

    def path_to(self, target_id: str) -> list[Unit]:
        """Return the units from the root down to the unit holding `target_id`, or to that unit itself."""
        for unit in self.root.iter_units():
            if unit.id == target_id or target_id in unit.member_refs or target_id == unit.lead:
                return self._path_from_root(unit)
        msg = f"'{target_id}' is not an agent or unit of this org."
        raise KeyError(msg)

    def _path_from_root(self, unit: Unit) -> list[Unit]:
        path = [unit]
        while path[0] is not self.root:
            path.insert(0, next(parent for parent in self.root.iter_units() if path[0] in parent.member_refs))
        return path
