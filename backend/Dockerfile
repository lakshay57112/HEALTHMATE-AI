FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN useradd -m appuser && mkdir -p /app/.data && chown -R appuser /app
USER appuser

EXPOSE 8000
# Apply migrations, make sure the food catalog + demo data exist, then serve.
# (Sample documents are committed in sample_docs/; regenerate with scripts/generate_samples.py.)
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
