# Backend image for Fly.io. Build context is the repo root (see .dockerignore). Built from git alone, so CI can deploy it.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
# PDFs are not in the image: production serves them from a private Supabase Storage bucket (deploy/upload_pdfs.py).
ENV ENV=production
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
