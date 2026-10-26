FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install the small set of shared-library dependencies used by the image
# processing stack.  The .dockerignore keeps datasets and local runtime state
# out of the context before this image is built.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY deployment/backend/requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt

# The default loader looks for /app/checkpoints/best_model.pth.  That model
# artifact is intentionally not versioned; .dockerignore keeps that one
# optional file available for an explicit local/deployment build while
# excluding alternate checkpoints.
COPY . /app

WORKDIR /app/deployment/backend

# Hugging Face Spaces and this image's command use 7860.  Local start.sh uses
# 8001 for the API and 3000 for the separately served frontend.
EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
