FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY --from=ghcr.io/astral-sh/uv:latest /uvx /bin/uvx

RUN useradd --create-home --shell /bin/bash app
USER app
WORKDIR /home/app

RUN uv tool install "fabricatio-agent[cli]" --python 3.13

ENTRYPOINT ["falcon"]