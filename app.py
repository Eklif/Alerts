from flask import Flask, render_template, request
from flask_socketio import SocketIO
from gtts import gTTS
import os
import time

app = Flask(__name__)
socketio = SocketIO(app)

# Папка для аудио
AUDIO_DIR = "alert_audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

# Очередь сообщений
messages = []

@app.route('/alert_audio/<filename>')
def serve_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)

@app.route('/')
def home():
    return render_template('alert_page.html')  # Страница для OBS

@app.route('/send_alert', methods=['POST'])
def handle_alert():
    text = request.form.get('text', '')
    username = request.form.get('username', 'Аноним')
    
    if not text:
        return "Нет текста", 400

    # Сохраняем сообщение
    message = f"{username}: {text}"
    messages.append(message)

    # Генерируем аудио (TTS)
    tts = gTTS(text=message, lang='ru')
    audio_path = os.path.join(AUDIO_DIR, f"alert_{int(time.time())}.mp3")
    tts.save(audio_path)

    # Отправляем в OBS через WebSocket
    socketio.emit('new_alert', {
        'text': message,
        'audio_path': audio_path
    })

    return "Сообщение отправлено!"

@app.route('/send', methods=['GET'])
def send_page():
    return render_template('send_alert.html')

if __name__ == '__main__':
    socketio.run(app, port=5001, host='0.0.0.0', debug=True, allow_unsafe_werkzeug=True, use_reloader=False)
