"""Shared error types for IncidentSherpa libs.

NotConfiguredError is the HONEST unconfigured state: a dependency whose
credentials have not landed yet (see BUILD-STATE.md BLOCKERS) raises it
loudly instead of no-opping or returning fake data. Callers (the API, the
worker) catch it and surface a clear 503 / blocked status.
"""


class NotConfiguredError(RuntimeError):
    """Raised when a sponsor dependency is not configured (missing env vars).

    The message MUST name the missing env vars and the BUILD-STATE.md
    blocker ID so a human knows exactly what to unblock.
    """


class UnexpectedResponseShapeError(RuntimeError):
    """A live API returned a shape the client cannot resolve.

    Claim integrity: parsers are tolerant about WHERE a value lives but
    never guess WHAT it is — an unresolvable response fails loudly with
    this error instead of substituting a made-up value.
    """
