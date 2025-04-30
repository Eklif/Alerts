# Должно быть абсолютно первыми строками!
from gevent import monkey
monkey.patch_all()

import werkzeug
werkzeug.cached_property = werkzeug.utils.cached_property

from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO
from gtts import gTTS
import os
import time
from collections import defaultdict
import time
from queue import Queue, Empty
from threading import Thread 


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'secret!')
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

# Функция обработки очереди
def process_queue():
    while processing_active:
        try:
            message, client_audio_path = alert_queue.get(timeout=1)  # Таймаут для периодической проверки флага
            
            # Отправка через WebSocket
            socketio.emit('new_alert', {
                'text': message,
                'audio_path': client_audio_path
            })
            
            # Задержка между сообщениями (1 секунда)
            time.sleep(1)
            alert_queue.task_done()
            
        except Empty:
            continue

# Запуск потока обработки
worker_thread = Thread(target=process_queue, daemon=True)
worker_thread.start()

@app.route('/send_alert', methods=['POST'])
def handle_alert():
    user_ip = request.remote_addr
    text = request.form.get('text', '').strip()
    username = request.form.get('username', 'Аноним').strip()
    
    if not text:
        return "Нет текста", 400

    current_time = time.time()
    cooldown = 5  # 5 секунд между сообщениями

    if current_time - ip_cooldown.get(user_ip, 0) < cooldown:
        remaining_time = cooldown - int(current_time - ip_cooldown[user_ip])
        return f"⏳ Подождите {remaining_time} сек. (ограничение по IP)", 429

    ip_cooldown[user_ip] = current_time

    message = f"{username}: {text}"
    messages.append(message)

    # Генерация аудио
    tts = gTTS(text=message, lang='ru')
    audio_filename = f"alert_{int(time.time())}.mp3"
    audio_path = os.path.join(AUDIO_DIR, audio_filename)
    tts.save(audio_path)
    
    client_audio_path = f"/alert_audio/{audio_filename}"
    
    # Добавление в очередь
    alert_queue.put((message, client_audio_path))
    return "Сообщение добавлено в очередь!"

@app.route('/send', methods=['GET'])
def send_page():
    return render_template('send_alert.html')
    
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
