"""Prompts are versioned artifacts (L2): one YAML file per prompt version under
/prompts, named <prompt_id>.<version>.yaml. The version string recorded with
every model call is '<prompt_id>@<version>#<sha8>' so an edited file can never
masquerade as the version it replaced."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from .config import get_settings


@dataclass(frozen=True)
class Prompt:
    prompt_id: str
    version: str
    system: str
    user_template: str
    sha: str

    @property
    def tag(self) -> str:
        return f"{self.prompt_id}@{self.version}#{self.sha}"

    def render(self, **kwargs: object) -> tuple[str, str]:
        return self.system, self.user_template.format(**kwargs)


@lru_cache
def load_prompt(prompt_id: str, version: str) -> Prompt:
    path = Path(get_settings().prompts_dir) / f"{prompt_id}.{version}.yaml"
    raw = path.read_bytes()
    data = yaml.safe_load(raw)
    if data.get("id") != prompt_id or data.get("version") != version:
        raise ValueError(f"prompt file {path} has mismatched id/version")
    return Prompt(
        prompt_id=prompt_id,
        version=version,
        system=data["system"],
        user_template=data.get("user", "{payload}"),
        sha=hashlib.sha256(raw).hexdigest()[:8],
    )


def assessor_variant(requested: str | None) -> str:
    if requested and requested != "default":
        return requested
    return get_settings().prompt_variant_assessor
