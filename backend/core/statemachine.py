"""State pattern, data-driven: one tiny class powers every workflow (user lifecycle, alert investigation, review)."""
from core.errors import Conflict


class StateMachine:
    def __init__(self, rules: dict[str, tuple[set[str], str]]):
        self.rules = rules  # action -> ({allowed source states}, target state)

    def apply(self, action: str, current: str) -> str:
        sources, target = self.rules[action]
        if current not in sources:
            raise Conflict(f"Cannot '{action}' from state '{current}'")
        return target

    def actions_from(self, current: str) -> list[str]:
        return [a for a, (sources, _) in self.rules.items() if current in sources]
