"""IncidentSherpa shared libraries.

Sub-packages are sponsor integration clients. Until credentials land
(BUILD-STATE.md BLOCKERS) every client factory raises NotConfiguredError —
never fake data, never silent no-ops.
"""

from libs.errors import NotConfiguredError

__all__ = ["NotConfiguredError"]
