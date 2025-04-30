from gevent import monkey
monkey.patch_all()

import werkzeug
werkzeug.cached_property = werkzeug.utils.cached_property

from flask import Flask, render_template, request, send_from_directory, jsonify
from flask_socketio import SocketIO
from gtts import gTTS
import os
import time
from collections import defaultdict
from queue import Queue, Empty
from threading import Thread
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'secret!')

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

socketio = SocketIO(app,
    async_mode='gevent',
    cors_allowed_origins="*",
    engineio_logger=True,
    logger=True
)

# Глобальные переменные
alert_queue = Queue()
ip_cooldown = defaultdict(float)
AUDIO_DIR = "alert_audio"
os.makedirs(AUDIO_DIR, exist_ok=True)
messages = []
processing_active = True  # Флаг для управления потоком обработки

@app.route('/')
def index():
    return "Сервер работает. Используйте /send для отправки сообщений."

# Функция обработки очереди
def process_queue():
    while processing_active:
        try:
            message, client_audio_path = alert_queue.get(timeout=1)
            
            logger.info(f"Отправка сообщения: {message[:50]}...")
            socketio.emit('new_alert', {
                'text': message,
                'audio_path': client_audio_path
            })
            
            time.sleep(1)
            alert_queue.task_done()
            
        except Empty:
            continue
        except Exception as e:
            logger.error(f"Ошибка в process_queue: {str(e)}")
            time.sleep(1)

# Запуск потока обработки
worker_thread = Thread(target=process_queue, daemon=True)
worker_thread.start()

@app.route('/send_alert', methods=['POST'])
def handle_alert():
    try:
        user_ip = request.remote_addr
        text = request.form.get('text', '').strip()
        username = request.form.get('username', 'Аноним').strip()
        
        if not text:
            return "Нет текста", 400

        current_time = time.time()
        cooldown = 5

        if current_time - ip_cooldown.get(user_ip, 0) < cooldown:
            remaining_time = cooldown - int(current_time - ip_cooldown[user_ip])
            return f"⏳ Подождите {remaining_time} сек.", 429

        ip_cooldown[user_ip] = current_time

        message = f"{username}: {text}"
        messages.append(message)

        # Генерация аудио
        try:
            tts = gTTS(text=message, lang='ru')
            audio_filename = f"alert_{int(time.time())}.mp3"
            audio_path = os.path.join(AUDIO_DIR, audio_filename)
            tts.save(audio_path)
            client_audio_path = f"/alert_audio/{audio_filename}"
        except Exception as e:
            logger.error(f"Ошибка генерации аудио: {str(e)}")
            return "Ошибка генерации аудио", 500
        
        alert_queue.put((message, client_audio_path))
        logger.info(f"Сообщение добавлено в очередь: {message[:50]}...")
        return "Сообщение добавлено в очередь!"

    except Exception as e:
        logger.error(f"Ошибка в handle_alert: {str(e)}")
        return "Внутренняя ошибка сервера", 500

@app.route('/alert_audio/<filename>')
def serve_audio(filename):
    try:
        return send_from_directory(AUDIO_DIR, filename)
    except FileNotFoundError:
        return "Аудиофайл не найден", 404

@app.route('/send', methods=['GET'])
def send_page():
    return render_template('send_alert.html')

@app.route('/healthcheck', methods=['GET'])
def healthcheck():
    return jsonify({
        "status": "ok",
        "queue_size": alert_queue.qsize(),
        "messages_processed": len(messages)
    })

if __name__ == '__main__':
    try:
        port = int(os.environ.get("PORT", 5000))  # Изменил на 5000 (стандартный для Railway)
        logger.info(f"Запуск сервера на порту {port}")
        socketio.run(app, host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"Ошибка запуска сервера: {str(e)}")
    finally:
        processing_active = False
        worker_thread.join()
