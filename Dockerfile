# TerraMind — single-container deploy for AWS EC2 free tier (t2/t3.micro, 1 GB RAM).
# No local LLM/embedding server: Groq (remote LLM) + fastembed (small ONNX
# embedding model, CPU, no torch) keep the container's memory footprint low
# enough to run alongside the OS on a 1 GB instance.

# ---------- Stage 1: frontend ----------
FROM node:20-slim AS webbuild
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_BASE=""
RUN npm run build

# ---------- Stage 2: backend ----------
FROM python:3.11-slim

RUN useradd -m -u 1000 user
ENV HOME=/home/user
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY Terramind_langgraph/ /app/
COPY --from=webbuild /web/dist /app/static

RUN mkdir -p /app/cache /app/src/vector /app/data \
    && chown -R user:user /app

USER user

ENV STATIC_DIR=/app/static \
    LLM_PROVIDER=groq \
    EMBED_PROVIDER=fastembed

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/api/health', timeout=3)" || exit 1

CMD ["uvicorn", "backend.app:socket_app", "--host", "0.0.0.0", "--port", "7860"]
