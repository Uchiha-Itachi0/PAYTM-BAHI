# The API as deployed (V8b): without Cognee, which stays on the laptop.
#
#   docker build -t bahi-api api/
#   docker run -p 8000:8000 -e DATABASE_URL=... -e SARVAM_API_KEY=... bahi-api
#
# Keys and the database URL come from the host's settings, never from a file in
# the image (.dockerignore keeps .env out).

FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

# The packages first, so a code change doesn't reinstall them. Only the app's
# own: no dev tools, no Cognee.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-default-groups --no-install-project

COPY . .

# Voice and the munshi on (the laptop defaults to off); Cognee off.
ENV PATH="/app/.venv/bin:$PATH" \
    SARVAM_OFFLINE=0 \
    COGNEE=off

# Render and Cloud Run say which port in $PORT. Behind their proxy, so the
# forwarded headers are trusted.
CMD ["sh", "-c", "exec uvicorn bahi.service:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
