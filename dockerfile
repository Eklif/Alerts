RUN which python && python --version
FROM python:3.10

# Устанавливаем FFmpeg и зависимости
RUN apt-get update && apt-get install -y ffmpeg

# Копируем код и устанавливаем Python-пакеты
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

CMD ["python", "app.py"]
