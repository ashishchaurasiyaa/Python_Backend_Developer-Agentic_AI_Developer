# TODO lab: a container running as root can do everything root can do on
# Linux -- write anywhere, bind ports below 1024, etc. If that container is
# ever compromised (a dependency with a vulnerability, an injection bug),
# the attacker inherits all of that. Dropping to a non-root user is one of
# the single highest-value, lowest-effort hardening steps you can take, and
# its effect is directly, mechanically testable -- not just a checkbox.
#
# This image creates a non-root user and gives it ownership of /app, but
# NEVER switches to it -- the container still runs as root by default.
#
# YOUR TASK: add a `USER appuser` line at the end, so the container actually
# runs as that user instead of root.
FROM alpine:3.20

RUN adduser -D -u 1000 appuser
WORKDIR /app
RUN chown appuser:appuser /app

# TODO: add `USER appuser` here

CMD ["sleep", "3600"]
