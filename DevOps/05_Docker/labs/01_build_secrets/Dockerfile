# TODO lab: an `ARG` value gets baked into the image's build HISTORY
# permanently -- anyone with the image (`docker history`, or just pulling
# and inspecting it) can read it back out, forever, even if the final image
# never "uses" it again at runtime. This is one of the most common real
# Docker security mistakes: a private package-registry token or API key
# passed via `--build-arg`, silently leaked to everyone who ever gets a copy
# of the image.
#
# BuildKit's `--mount=type=secret` is the fix: the secret is made available
# to ONE `RUN` step as a file, used, and then never written to any layer or
# recorded in history at all.
#
# YOUR TASK: replace the ARG-based approach below with a secret mount:
#
#   RUN --mount=type=secret,id=token \
#       echo "using token: $(cat /run/secrets/token)" && echo "build step complete"
#
# (delete the `ARG SECRET_TOKEN` line entirely -- it's no longer needed)
# syntax=docker/dockerfile:1
FROM alpine:3.20

ARG SECRET_TOKEN
RUN echo "using token: ${SECRET_TOKEN}" && echo "build step complete"
