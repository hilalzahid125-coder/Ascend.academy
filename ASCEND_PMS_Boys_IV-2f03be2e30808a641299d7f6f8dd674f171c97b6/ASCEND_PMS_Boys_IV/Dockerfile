FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /data/uploads /data/backups
ENV PMS_SECURE_COOKIE=1
ENV PMS_DATA_DIR=/data
EXPOSE 8000
CMD ["sh","-c","uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
