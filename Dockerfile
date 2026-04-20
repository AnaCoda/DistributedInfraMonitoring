FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -s /root/.local/bin/uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

# Build the env at image-build time
RUN uv sync --frozen --no-editable

COPY . .

CMD ["/app/.venv/bin/python", "-u", "runner.py"]