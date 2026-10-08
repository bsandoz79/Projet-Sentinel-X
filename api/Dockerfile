FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV DB_PATH=/data/sentinel.db PHOTOS_DIR=/data/photos PYTHONUNBUFFERED=1
EXPOSE 8000
# 127.0.0.1 par défaut : l'API n'est joignable que par le dashboard sécurisé (nginx) sur le Pi
ENV API_HOST=127.0.0.1
CMD uvicorn main:app --host "$API_HOST" --port 8000
