# ==============================================================================
# Document-Analyzer-MomoWarriors
#
# Single container: nginx serves the static frontend (frontend/) and reverse
# proxies /api/ to a FastAPI backend (app.main:app) run by uvicorn on 8000.
# Both processes are supervised by supervisord so the container stays up (and
# restarts a crashed process) instead of the old `cmd1 & cmd2` shell trick,
# where the container kept running even if uvicorn silently died.
# ==============================================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# nginx to serve/proxy, supervisor to run both processes, curl for the healthcheck
RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx supervisor curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Python deps (this uses the patched requirements.txt with fastapi/uvicorn/
#     python-multipart added — see accompanying file) ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Backend ---
COPY app ./app

# Data dirs the app writes to at runtime (uploaded PDFs + Chroma vector store)
RUN mkdir -p ./data/pdf ./data/vector_store

# --- Frontend (static, no build step) ---
COPY frontend /usr/share/nginx/html

# Point the frontend at the API through nginx's reverse proxy instead of the
# hardcoded http://127.0.0.1:8000 (which only ever resolves to the *browser's*
# machine, not this container). See nginx.conf's `location /api/` block.
RUN sed -i 's|http://127.0.0.1:8000|/api|g' /usr/share/nginx/html/index.html

# --- Nginx + supervisor config ---
COPY nginx.conf /etc/nginx/sites-available/default
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Only port 80 needs to be published; nginx reverse-proxies to uvicorn
# internally, so 8000 never needs to be exposed to the outside world.
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://127.0.0.1/api/health || exit 1

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
