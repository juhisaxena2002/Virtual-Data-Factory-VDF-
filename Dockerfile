# syntax=docker/dockerfile:1
#
# synthgen — containerised CLI.
#
# The image's entrypoint IS the `synthgen` command, so the container
# behaves exactly like the local tool:
#
#   docker run --rm <image> "100 fake users" --backend anthropic
#   docker run --rm -it <image> "iot sensors" --stream --backend anthropic
#
# A one-off generation prints JSON and exits. A `--stream` run keeps
# producing records until the container is stopped (Ctrl+C with -it,
# or `docker stop`).

FROM python:3.12-slim

# libgomp1 is required at runtime by the CPU build of PyTorch.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

# HF_HOME fixes the model cache location so the embedding model baked in
# below is found at runtime. PYTHONUNBUFFERED keeps streamed output
# flowing promptly when stdout is piped rather than a TTY.
ENV HF_HOME=/opt/hf-cache \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

# Install the CPU-only torch wheel FIRST so sentence-transformers does
# not pull the multi-GB CUDA build, then install synthgen with both
# LLM backends (anthropic + gemini).
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir ".[all]"

# Bake the spec-cache embedding model into the image so the container
# never downloads it at runtime and works fully offline.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Drop root.
RUN useradd --create-home --uid 1000 app \
 && chown -R app:app /opt/hf-cache
USER app

ENTRYPOINT ["synthgen"]
CMD ["--help"]
