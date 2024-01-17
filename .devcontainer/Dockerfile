FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

COPY requirements.txt /tmp/requirements.txt

RUN apt-get update \
  && apt-get install --no-install-recommends -y poppler-utils bash-completion \
  && pip install -U pip \
  && pip install -r /tmp/requirements.txt ipykernel