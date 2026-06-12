"""Guild.ai control plane client — REST descope path (see libs/guild/descope.md).

Real REST session/audit client in libs/guild/session.py: one session per
incident, append-only audit events, close on resolve. Raises
NotConfiguredError naming B1 while GUILD_PAT / GUILD_API_BASE are unset
(BUILD-STATE.md). Never returns fake sessions or fake audit entries.
"""

from __future__ import annotations

from libs.guild.session import append_audit_event, close_session, create_session

__all__ = ["append_audit_event", "close_session", "create_session"]
