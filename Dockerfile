# Stickman Studio as a hosted website (STUDIO_MODE=hosted). See DEPLOY.md.

# 1) build the dashboard
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY web/ ./
RUN npm run build

# 2) the app
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg espeak-ng libsndfile1 ca-certificates \
 && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1000 studio
WORKDIR /app
COPY requirements.txt requirements-paid.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-paid.txt
COPY studio/ studio/
COPY --from=web /web/dist web/dist
ENV STUDIO_MODE=hosted \
    STUDIO_DATA_DIR=/data/data \
    STUDIO_PROJECTS_DIR=/data/projects \
    STUDIO_ENV_FILE=/data/.env \
    STUDIO_TRUST_PROXY=1 \
    PORT=8765 \
    PYTHONUNBUFFERED=1
RUN mkdir -p /data && chown studio:studio /data
USER studio
VOLUME /data
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health')"
CMD ["python", "-m", "studio", "serve", "--host", "0.0.0.0"]
