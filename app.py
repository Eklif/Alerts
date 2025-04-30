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
from queue import Queue
from threading import Thread 


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'secret!')
socketio = SocketIO(app,
    async_mode='gevent',
    cors_allowed_origins="*",  # Разрешить все домены
    engineio_logger=True,      # Логирование для диагностики
    logger=True               
)
@socketio.on('connect')
def handle_connect():
    print('Client connected')
    
#Очередь для сообщенией
alert_queue=Queue()   
#словарь для хранения времени последнго сообщения  
ip_cooldown = defaultdict(float)

# Папка для аудио (временная, на Railway файлы не сохраняются после перезапуска)
AUDIO_DIR = "alert_audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

messages = []

# Функция обработки сообщений из очереди
def process_queue():
    while True:
        # Получаем сообщение из очереди (блокирующий вызов)
        message,client_audio_path=alert_queue.get()

        # Отправляем через WebSocket
        socketio.emit('new_alert', {
            'text':message,
            'audio_path':client_audio_path
            })
        # Помечаем задачу как выполненную
        time.sleep(56)
        alert_queue.task_done()
        
        
# Запускаем обработчик очереди в отдельном потоке
worker_thread=Thread(target=process_queue, daemon=True)
worker_thread.start()
alert_queue.join()

@app.route('/alert_audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)

@app.route('/')
def home():
    return render_template('alert_page1.html')

@app.route('/send_alert', methods=['POST'])
def handle_alert():
    user_ip=request.remote_addr #IP пользователя
    text = request.form.get('text', '')
    username = request.form.get('username', 'Аноним')
    
    if not text:
        return "Нет текста", 400

    current_time=time.time()
    cooldown=5 #10 сек межжду соообщениями

    if current_time-ip_cooldown.get(user_ip,0)<cooldown:
        remaining_time=cooldown-int(current_time-ip_cooldown[user_ip])
        return f"⏳ Подождите {remaining_time} сек. (ограничение по IP)", 429

    ip_cooldown[user_ip]=current_time

    message = f"{username}: {text}"
    messages.append(message)

    # Генерируем аудио
    tts = gTTS(text=message, lang='ru')
    audio_filename=f"alert_{int(time.time())}.mp3"
    audio_path = os.path.join(AUDIO_DIR, audio_filename)
    tts.save(audio_path)
    
    # Клиентский путь (такой же, как раньше)
    client_audio_path=f"/alert_audio/{audio_filename}"
    # Добавляем сообщение в очередь
    alert_queue.put((message, client_audio_path))
    return "Сообщение добавлено в очередь!"

@app.route('/send', methods=['GET'])
def send_page():
    return render_template('send_alert.html')
    
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
