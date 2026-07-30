from flask import Flask, render_template, request, redirect, session
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)

app.secret_key = os.environ.get('SECRET_KEY', 'dev-fallback-key')
app.permanent_session_lifetime = timedelta(hours=1)

socketio = SocketIO(app)

def get_db():
    return psycopg2.connect(os.environ.get('DATABASE_URL'))

@app.route('/group/1', methods=['GET', 'POST'])
def home():
    username = session.get('username', '<anonymous>')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT sender_name, content, sent_at FROM messages ORDER BY sent_at DESC LIMIT 50")
    messages = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('chat_room.html', current_user=username, messages=messages)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    username = request.form['username']
    password = request.form['password']

    password_hash = generate_password_hash(password)
    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
            (username, password_hash)
        )
        conn.commit()
        cur.close()
        conn.close()
        return redirect('/login')
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        cur.close()
        conn.close()
        return render_template('register.html', error="Username is already taken")
    



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    username = request.form['username']
    password = request.form['password']

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, password_hash, username FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user and check_password_hash(user[1], password):
        session.permanent = True
        session['username'] = user[2]
        return redirect('/group/1') 
    return render_template('login.html', error="Wrong password or username")

@socketio.on('send_message')
def handle_message(data):
    username = session.get('username', '<anonymous>')
    content = data['content']

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (sender_name, content) VALUES (%s, %s)",
        (username, content)
    )
    conn.commit()
    conn.close()
    cur.close()

    emit('new_message', {'sender': username, 'content': content}, broadcast=True)


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/group/1')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, debug=True, host='0.0.0.0', port=port)