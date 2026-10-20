# Backend image for Fly.io. Build context is the repo root (see .dockerignore).
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
# Only the public (citable) PDFs are shipped; solution PDFs are never in the image. See deploy/make_pdfs.py.
COPY deploy/pdfs ./pdfs
ENV ENV=production BB_PDF_DIR=/srv/pdfs
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
