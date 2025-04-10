from gevent import monkey
monkey.patch_all() 

from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO
from gtts import gTTS
import os
import time


app = Flask(__name__)
socketio = SocketIO(app, async_mode='gevent', cors_allowed_origins="*")

# Папка для аудио (временная, на Railway файлы не сохраняются после перезапуска)
AUDIO_DIR = "alert_audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

messages = []

@app.route('/alert_audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)

@app.route('/')
def home():
    return render_template('alert_page.html')

@app.route('/send_alert', methods=['POST'])
def handle_alert():
    text = request.form.get('text', '')
    username = request.form.get('username', 'Аноним')
    
    if not text:
        return "Нет текста", 400

    message = f"{username}: {text}"
    messages.append(message)

    # Генерируем аудио
    tts = gTTS(text=message, lang='ru')
    audio_path = os.path.join(AUDIO_DIR, f"alert_{int(time.time())}.mp3")
    tts.save(audio_path)

    # Отправляем через WebSocket
    socketio.emit('new_alert', {
        'text': message,
        'audio_path': f"/alert_audio/{os.path.basename(audio_path)}"  # Правильный путь для клиента
    })

    return "Сообщение отправлено!"

@app.route('/send', methods=['GET'])
def send_page():
    return render_template('send_alert.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))  # Используйте порт из переменной Railway
    socketio.run(app, host='0.0.0.0', port=port)
