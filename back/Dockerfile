# Stage 1: Builder - install dependencies and build environment
FROM python:3.10-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsm6 libxext6 libsndfile1 build-essential cmake \
    libgl1-mesa-glx libglib2.0-0 pkg-config libffi-dev libssl-dev git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements to leverage cache
COPY requirements.txt .

# Upgrade pip and install dependencies locally to /install
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --prefix=/install --prefer-binary --retries=5 --timeout=60 -r requirements.txt


# Stage 2: Final image - copy only installed packages and app code
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Reinstall system deps needed at runtime (you might skip build-essential & cmake here if not needed at runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsm6 libxext6 libsndfile1 libgl1-mesa-glx libglib2.0-0 pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy installed python packages from builder stage
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

EXPOSE 8000

# Run gunicorn with 3 workers (adjust workers based on CPU cores if you want)
CMD ["gunicorn", "backend.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
