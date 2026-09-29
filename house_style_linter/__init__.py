"""House-style linter: deterministic checks for copy, standard library only."""
from .core import Finding, lint_text
from .options import ConfigError, Options, load_config
from .rules import RULES, RULES_BY_ID

__version__ = "0.1.0"
__all__ = ["Finding", "lint_text", "Options", "load_config", "ConfigError", "RULES", "RULES_BY_ID", "__version__"]
