FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/models

RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# bake the default embedding model into the image so the container starts offline
RUN python -c "from doctrace.embed import Embedder; Embedder('sentence-transformers/all-MiniLM-L6-v2')"

ENV DOCTRACE_HOST=0.0.0.0 \
    DOCTRACE_DATA_DIR=/data \
    DOCTRACE_INDEX_DIR=/index \
    DOCTRACE_ALLOW_OPEN=0 \
    OLLAMA_AUTOSTART=0
EXPOSE 7860
VOLUME ["/index"]

# update the index, then serve the UI (it keeps working even if indexing fails)
CMD ["sh", "-c", "python ingest.py; exec python search_app.py --no-browser"]
