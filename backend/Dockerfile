FROM python:3.11-slim-bookworm

WORKDIR /app

# System dependencies for PaddleOCR, OpenCV, pdf2image
RUN apt-get update && apt-get install -y --no-install-recommends \
    # OpenCV runtime dependencies
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    # For pdf2image (PDF -> image conversion)
    poppler-utils \
    # OpenMP (used by PaddlePaddle for CPU parallelism)
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download PaddleOCR models during build to avoid first-run latency
# This triggers model download and caches them in /root/.paddleocr/
RUN python -c "from paddleocr import PaddleOCR; ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False); print('PaddleOCR models downloaded successfully')"

# Create uploads directory
RUN mkdir -p /app/uploads

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
