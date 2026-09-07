# TODO lab: `COPY requirements.txt . && RUN pip install` (the fix from
# ../../practical/01_docker_lab.md Lab 1) avoids re-running pip install when
# only APP CODE changes. It does NOT help when requirements.txt ITSELF
# changes -- that busts the layer's cache and pip re-downloads every
# package from PyPI again, even ones that haven't changed version.
#
# `RUN --mount=type=cache,target=<dir>` fixes THAT: it gives the RUN step a
# persistent directory that survives across separate `docker build` runs
# (unlike a normal layer, its contents are never baked into the image) --
# point it at pip's own download cache, and pip finds packages it already
# fetched even when the layer itself has to re-run.
#
# YOUR TASK: add a cache mount to the pip install line:
#
#   RUN --mount=type=cache,target=/root/.cache/pip \
#       pip install -r requirements.txt
# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
