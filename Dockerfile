# Dwarpal gateway + demo API. The playground (frontend/) is deployed separately.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY dwarpal/ dwarpal/
COPY demo/ demo/
COPY api/ api/

RUN useradd --create-home --uid 10001 dwarpal
USER 10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"

# Keys come from the environment at run time, never from the image:
#   docker run -p 8000:8000 -e GROQ_API_KEY=... dwarpal
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
