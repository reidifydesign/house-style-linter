"""Options and the optional JSON config file."""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Optional, Tuple

DEFAULT_RATIONED = ("journey", "discover", "invisible")

_LIST_KEYS = {
    "banned_phrases": "extra_banned",
    "rationed_words": "rationed_words",
    "disable": "disable",
    "protected_lines": "protected_lines",
}


@dataclass(frozen=True)
class Options:
    """What to check and how strictly.

    require_next_step is off by default: a closing action only makes sense for client
    facing copy. Turn it on for a run, or mark a single file with a `house-style:
    client-facing` line near the top.
    """

    require_next_step: bool = False
    max_words: Optional[int] = None
    disable: Tuple[str, ...] = ()
    extra_banned: Tuple[str, ...] = ()
    rationed_words: Tuple[str, ...] = DEFAULT_RATIONED
    protected_lines: Tuple[str, ...] = ()
    include_code: bool = False


class ConfigError(ValueError):
    pass


def load_config(path: str, base: Optional[Options] = None) -> Options:
    """Read a JSON config file and apply it on top of `base`."""
    opts = base or Options()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ConfigError("cannot read config %s: %s" % (path, exc))
    if not isinstance(data, dict):
        raise ConfigError("config %s must be a JSON object" % path)
    known = set(_LIST_KEYS) | {"require_next_step", "max_words"}
    unknown = sorted(set(data) - known)
    if unknown:
        raise ConfigError("config %s has unknown keys: %s" % (path, ", ".join(unknown)))
    changes = {}
    for key, field_name in _LIST_KEYS.items():
        if key in data:
            value = data[key]
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ConfigError("config key %r must be a list of strings" % key)
            changes[field_name] = tuple(value)
    if "require_next_step" in data:
        if not isinstance(data["require_next_step"], bool):
            raise ConfigError("config key 'require_next_step' must be true or false")
        changes["require_next_step"] = data["require_next_step"]
    if "max_words" in data:
        mw = data["max_words"]
        if mw is not None and (not isinstance(mw, int) or isinstance(mw, bool) or mw < 1):
            raise ConfigError("config key 'max_words' must be a positive whole number")
        changes["max_words"] = mw
    return replace(opts, **changes)
