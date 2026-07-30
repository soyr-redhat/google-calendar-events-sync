FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY main.py .

ENV UV_CACHE_DIR=/tmp/uv-cache

USER 1001

CMD ["uv", "run", "main.py"]
