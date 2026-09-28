FROM ghcr.io/astral-sh/uv:0.12.17@sha256:10787c682e4184e4f290de1171fd4703dc63de99221f10fe1c99002ce7fa9acc AS uv
FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e

COPY --from=uv /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY config ./config
COPY ops/migrations ./ops/migrations
COPY data/corpus ./data/corpus
COPY data/captures ./data/captures

RUN uv sync --frozen --no-dev \
    && useradd --create-home --uid 10001 incidentgraph \
    && mkdir -p /app/data/runtime/app-traces /app/models \
    && chown -R incidentgraph:incidentgraph /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/app/models/huggingface \
    TRANSFORMERS_CACHE=/app/models/huggingface

USER 10001:10001
EXPOSE 8000
CMD ["incidentgraph-api"]
