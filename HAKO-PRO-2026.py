import tkinter as tk
from tkinter import messagebox, colorchooser
import requests
import hashlib
import uuid
import platform
import threading
import time
import webbrowser
import ctypes
import sys
import os
import json 
# import atexit # Non nécessaire, WM_DELETE_WINDOW gère la fermeture propre

# ============================
# CONFIG
# ============================
DOWNLOAD_LINK = "https://mega.nz/folder/sNMX2ZDT#MsXmCAafZuymxFH8XmEL7w"  # Lien logiciel
WORKER_URL = "https://spring-glade-0359.mercifoi435.workers.dev/"      # Worker (Vérifiez si cette URL est correcte !)
DEFAULT_FONT = "Segoe UI"
ALT_FONTS = ["Consolas", "Courier New", "Arial", "Calibri", "Verdana"]
LICENSE_FILE = "license.dat" # Fichier pour la persistance de la clé

# ============================
# UTIL : HWID & Persistence
# ============================
def get_hwid():
    """Génère un HWID stable basé sur des identifiants système."""
    raw = platform.node() + platform.system() + platform.machine() + str(uuid.getnode())
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def save_license_data(data):
    """Sauvegarde les données de licence dans un fichier local."""
    try:
        with open(LICENSE_FILE, 'w') as f:
            json.dump(data, f)
    except IOError as e:
        print(f"Erreur lors de la sauvegarde du fichier de licence: {e}")

def load_license_data():
    """Charge les données de licence depuis un fichier local."""
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            # Si le fichier existe mais est corrompu, on le supprime
            os.remove(LICENSE_FILE)
            print(f"Fichier de licence corrompu/illisible. Suppression: {e}")
            return None
    return None

def delete_local_license():
    """Supprime le fichier de licence localement."""
    if os.path.exists(LICENSE_FILE):
        try:
            os.remove(LICENSE_FILE)
            return True
        except Exception as e:
            print(f"Erreur lors de la suppression du fichier de licence: {e}")
            return False
    return True

# ============================
# LICENCE LOGIC (Worker Cloudflare)
# ============================
def check_and_bind_key(key):
    """Vérifie la licence via le Worker Cloudflare et retourne tuple (ok, message, data)."""
    hwid = get_hwid()
    try:
        r = requests.post(WORKER_URL, json={"license": key, "hwid": hwid}, timeout=10)
        r.raise_for_status()
        data = r.json()

        if not data.get("valid", False):
            error_msg = data.get("error", "Erreur inconnue du Worker.")
            return False, error_msg, None

        return True, "activated" if data.get("hwid") == hwid else "already_bound", data

    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code
        return False, f"Erreur de l'API: {status_code}. Vérifiez l'URL du Worker.", None
    except requests.exceptions.ConnectionError:
        return False, "Erreur de connexion réseau (Connexion refusée ou DNS échoué).", None
    except requests.exceptions.Timeout:
        return False, "Délai d'attente dépassé (Worker lent).", None
    except requests.exceptions.RequestException as e:
        return False, f"Erreur réseau générale: {e}", None
    except ValueError:
        return False, "Réponse invalide du Worker (JSON mal formé).", None

# ============================
# UI : THEME / STYLES & ANIMATION
# ============================
PRIMARY_BG = "#0b0016"
PANEL_BG = "#120022"
NEON_PINK = "#ff2df2"
NEON_PULSE_COLORS = ["#ff2df2", "#d400ff", "#ff66cc", "#ff00aa", "#cc00ff", "#00fff2", "#00ff66"]
PULSE_SPEED_MS = 300

def menu_bg_pulse(widget, app, idx=[0]):
    """Anime le fond du menu avec un effet de couleur pulsée néon (plus subtil)."""
    if not app.running:
        return
    
    # 1. Calcul de la couleur de fond
    color = NEON_PULSE_COLORS[idx[0] % len(NEON_PULSE_COLORS)]
    try:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        # Assombrir la couleur pour le fond du menu (effet "basse fréquence" du néon)
        dark_color = f"#{r//5:02x}{g//5:02x}{b//5:02x}" 
    except ValueError:
        dark_color = "#080012" # Fallback color

    widget.configure(bg=dark_color)
    
    idx[0] += 1
    # Stocker l'ID de l'animation pour pouvoir l'arrêter proprement
    # Attention: Si 'app' est détruit avant 'after' mais 'running' est toujours True, cela peut causer un crash.
    # L'appel à 'after' doit être la dernière chose faite dans le thread principal.
    if app.running:
        app.pulse_job = widget.after(PULSE_SPEED_MS, lambda: menu_bg_pulse(widget, app, idx))

# ============================
# MAIN APP
# ============================
class HakoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Hako Rachon Launcher V4 PRO — Quantum")
        self.geometry("760x460")
        self.resizable(False, False)
        self.running = True
        self.pulse_job = None # ID du job pour l'animation Tkinter
        
        # Initialiser les couleurs et la police
        self.theme_colors = {
            "primary_bg": PRIMARY_BG,
            "panel_bg": PANEL_BG,
            "neon_accent": NEON_PINK,
            "text_fg": "#d4b3ff",
            "button_bg": "#0a0018",
        }
        self.current_font = DEFAULT_FONT
        self.license_data = None
        self.configure(bg=self.theme_colors["primary_bg"])
        
        # Setup Widgets
        self.setup_ui()
        
        # Tente de charger et de vérifier la licence au démarrage
        self.load_initial_license() 
        
        # Le protocole WM_DELETE_WINDOW garantit un arrêt propre lors de la fermeture de la fenêtre.
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        

    def load_initial_license(self):
        """Charge la clé sauvegardée et vérifie sa validité via le Worker en arrière-plan."""
        saved_data = load_license_data()
        # Assurez-vous que la page "home" est initialisée avant d'y accéder
        if "home" not in self.pages:
            self.pages["home"] = HomePage(self.container, self)
            
        self.pages["home"].set_buttons_active(False) # Désactiver le bouton d'activation pendant la vérification initiale

        if saved_data and saved_data.get("license"):
            key = saved_data["license"]
            self.pages["home"].key_var.set(key) # Pré-remplit le champ
            self.pages["home"].set_status("Vérification de la licence sauvegardée... (Réseau)", "#ffcc00")
            self.config(cursor="watch") # Curseur de chargement
            
            # Lance la vérification réseau dans un thread
            threading.Thread(target=lambda: self._check_saved_key(key)).start()
        else:
            self.show_home() # Afficher l'accueil normal si aucune clé n'est sauvegardée
            self.pages["home"].set_buttons_active(True)
            self.pages["home"].set_status("Entrez une clé PRO pour activer.")

    def _check_saved_key(self, key):
        """Vérification réseau pour la clé sauvegardée."""
        ok, msg, license_data = check_and_bind_key(key)
        self.after(0, lambda: self._handle_saved_check_result(ok, msg, license_data, key))

    def _handle_saved_check_result(self, ok, msg, license_data, key):
        """Met à jour l'interface après la vérification de la clé sauvegardée."""
        home_page = self.pages["home"]
        self.config(cursor="") # Réinitialiser le curseur

        if ok:
            # Clé valide
            self.save_license_data(license_data)
            home_page.set_status("Licence valide, Bienvenue.", self.theme_colors["neon_accent"])
            self.show_download_page(license_data) # Va directement à la page de téléchargement
        else:
            # Clé invalide ou erreur réseau/HWID
            delete_local_license() # Supprimer la clé invalide localement
            home_page.set_buttons_active(True)
            home_page.set_status(f"Licence expirée/invalide. Veuillez entrer une clé. (Erreur: {msg})", "#ff4444")
            self.show_home()
            
    def save_license_data(self, data):
        """Fonction wrapper pour la sauvegarde de la clé."""
        self.license_data = data
        save_license_data(data)

    def setup_ui(self):
        # Barre supérieure
        self.top = tk.Frame(self, bg=self.theme_colors["panel_bg"], height=70)
        self.top.pack(fill="x", side="top")
        self.top_title = tk.Label(self.top, text="HAKO RACHON LAUNCHER V4 PRO",
                                 bg=self.theme_colors["panel_bg"], fg=self.theme_colors["neon_accent"],
                                 font=(self.current_font, 20, "bold"))
        self.top_title.pack(side="left", padx=16, pady=8)
        self.top_hwid_text = f"HWID: {get_hwid()[:12]}..."
        self.top_hwid = tk.Label(self.top, text=self.top_hwid_text, bg=self.theme_colors["panel_bg"],
                                 fg=self.theme_colors["text_fg"], font=("Consolas", 10))
        self.top_hwid.pack(side="right", padx=12)

        # Menu de gauche RGB
        self.menu = tk.Frame(self, bg=self.theme_colors["panel_bg"], width=200)
        self.menu.place(x=0, y=70, height=390)
        self.menu_buttons = []

        self.pages = {}
        
        btn_cfg = [
            ("HOME", self.show_home),
            ("OPTIONS", self.show_options),
            ("SYS INFO", self.show_info),
            ("SUPPORT", self.show_support),
        ]
        
        # Initialisation des pages (les placer ici assure qu'elles existent avant load_initial_license)
        self.container = tk.Frame(self, bg=self.theme_colors["primary_bg"])
        self.container.place(x=200, y=70, width=560, height=390)
        self.pages["home"] = HomePage(self.container, self)
        self.pages["options"] = OptionsPage(self.container, self)
        self.pages["info"] = InfoPage(self.container, self)
        self.pages["support"] = SupportPage(self.container, self)
        
        for i, (t, cmd) in enumerate(btn_cfg):
            b = tk.Button(self.menu, text=t, command=cmd,
                          bg=self.theme_colors["button_bg"], fg=self.theme_colors["neon_accent"],
                          font=(self.current_font, 11, "bold"), relief="flat", 
                          activebackground=self.theme_colors["neon_accent"], 
                          activeforeground=self.theme_colors["button_bg"], 
                          borderwidth=0 # Look pro
                          ) 
            b.place(x=10, y=10 + i*50, width=180, height=40)
            self.menu_buttons.append(b)
            
        # Start the pulsing background animation
        # La première exécution initialise self.pulse_job
        self.pulse_job = self.menu.after(0, lambda: menu_bg_pulse(self.menu, self)) 

    def on_closing(self):
        # 1. Signaler l'arrêt
        self.running = False
        
        # 2. Arrêter l'animation (CRITIQUE pour le blocage)
        if self.pulse_job:
            try:
                # Tente d'annuler le job planifié
                self.after_cancel(self.pulse_job)
                self.pulse_job = None
            except Exception as e:
                print(f"Avertissement: Impossible d'annuler l'animation Tkinter: {e}")
        
        # 3. Forcer l'arrêt de la boucle Tkinter (pour les threads internes)
        # Ceci est la principale modification pour garantir un arrêt immédiat.
        try:
            self.quit() 
        except Exception as e:
            print(f"Avertissement: Impossible d'appeler self.quit(): {e}")
            
        # 4. Détruire la fenêtre principale
        self.destroy() 


    def hide_all(self):
        for p in self.pages.values():
            p.place_forget()

    def show_home(self):
        self.hide_all()
        
        # NOUVELLE LOGIQUE : Si la licence est active, le bouton HOME redirige vers la page de téléchargement.
        if self.license_data:
            self.show_download_page(self.license_data)
        else:
            # Si aucune licence n'est chargée, afficher la page d'accueil d'activation.
            self.pages["home"].place(x=0, y=0, relwidth=1, relheight=1)
            self.pages["home"].set_buttons_active(True)
            self.pages["home"].set_status("Entrez une clé PRO pour activer.")

    def show_download_page(self, license_data):
        self.license_data = license_data
        self.hide_all()
        if "download" not in self.pages:
            self.pages["download"] = DownloadPage(self.container, self, self.license_data)
        else:
            self.pages["download"].update_content(self.license_data)
        self.pages["download"].place(x=0, y=0, relwidth=1, relheight=1)

    def show_options(self):
        self.hide_all()
        self.pages["options"].place(x=0, y=0, relwidth=1, relheight=1)

    def show_info(self):
        self.hide_all()
        self.pages["info"].place(x=0, y=0, relwidth=1, relheight=1)

    def show_support(self):
        self.hide_all()
        self.pages["support"].place(x=0, y=0, relwidth=1, relheight=1)

    def change_color(self, key, title):
        """Ouvre le sélecteur de couleur et met à jour le thème."""
        color_code = colorchooser.askcolor(title=f"Choisir la couleur pour: {title}")
        if color_code and color_code[1]: # (rgb_tuple, hex_code)
            hex_color = color_code[1]
            self.theme_colors[key] = hex_color
            self.apply_theme()
            messagebox.showinfo("Couleur Changée", f"'{title}' mis à jour en {hex_color}.")
            
    def set_font(self, font_name):
        """Change la police principale de l'application et applique le thème."""
        self.current_font = font_name
        self.apply_theme()
        messagebox.showinfo("Police Changée", f"La police principale est maintenant : {font_name}.")

    def apply_theme(self):
        """Applique les couleurs et la police du thème à l'application principale et à toutes les pages."""
        
        # 1. Mise à jour de la fenêtre principale et de la barre supérieure
        self.configure(bg=self.theme_colors["primary_bg"])
        self.top.configure(bg=self.theme_colors["panel_bg"])
        self.top_title.configure(
            bg=self.theme_colors["panel_bg"], 
            fg=self.theme_colors["neon_accent"],
            font=(self.current_font, 20, "bold")
        )
        self.top_hwid.configure(bg=self.theme_colors["panel_bg"], fg=self.theme_colors["text_fg"])
        self.container.configure(bg=self.theme_colors["primary_bg"])
        
        # 2. Mise à jour des boutons du menu 
        self.menu.configure(bg=self.theme_colors["button_bg"]) # Le pulse gère le fond, mais on donne une base
        for button in self.menu_buttons:
            button.configure(
                font=(self.current_font, 11, "bold"),
                bg=self.theme_colors["button_bg"], 
                fg=self.theme_colors["neon_accent"],
                activebackground=self.theme_colors["neon_accent"], 
                activeforeground=self.theme_colors["button_bg"]
            )
            
        # 3. Mettre à jour les pages (y compris la page de téléchargement si elle existe)
        for page_name, page in self.pages.items():
            if hasattr(page, 'update_theme'):
                page.update_theme()
            


# ============================
# PAGES (Home, Download, Options, Info, Support)
# ============================

class HomePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=app.theme_colors["primary_bg"])
        self.app = app
        
        self.title_label = tk.Label(self, text="Welcome to Hako Rachon Launcher V4 PRO", 
                                     bg=app.theme_colors["primary_bg"],
                                     fg=app.theme_colors["neon_accent"], 
                                     font=(app.current_font, 18, "bold"))
        self.title_label.pack(pady=12)
        
        self.subtitle_label = tk.Label(self, text="Enter your license below to activate (first use binds HWID).",
                                         bg=app.theme_colors["primary_bg"], 
                                         fg=app.theme_colors["text_fg"],
                                         font=(app.current_font, 10))
        self.subtitle_label.pack(pady=6)

        entry_frame = tk.Frame(self, bg=app.theme_colors["primary_bg"])
        entry_frame.pack(pady=8)
        self.key_var = tk.StringVar()
        self.entry_key = tk.Entry(entry_frame, textvariable=self.key_var, width=38, font=("Consolas", 12),
                                 bg="#120022", fg="#ffb7ff", insertbackground="#ffffff", borderwidth=1, relief="solid")
        self.entry_key.grid(row=0, column=0, padx=4, ipady=4)

        self.act_btn = tk.Button(entry_frame, text="Activate", 
                                 bg=app.theme_colors["neon_accent"], fg="#111",
                                 font=(app.current_font, 11, "bold"), command=self.activate_key, borderwidth=0, relief="raised")
        self.act_btn.grid(row=0, column=1, padx=6)

        self.status_label = tk.Label(self, text="", bg=app.theme_colors["primary_bg"], fg="#b3a0ff", font=(app.current_font, 10))
        self.status_label.pack(pady=6)

    def set_status(self, text, color="#b3a0ff"):
        """Fonction utilitaire pour mettre à jour le statut et la couleur."""
        self.status_label.config(text=text, fg=color)

    def set_buttons_active(self, active):
        """Active ou désactive les éléments interactifs pendant les opérations réseau."""
        state = tk.NORMAL if active else tk.DISABLED
        self.entry_key.config(state=state)
        self.act_btn.config(state=state)

    def update_theme(self):
        """Met à jour les couleurs et les polices des widgets de la page."""
        self.configure(bg=self.app.theme_colors["primary_bg"])
        self.title_label.configure(
            bg=self.app.theme_colors["primary_bg"], 
            fg=self.app.theme_colors["neon_accent"],
            font=(self.app.current_font, 18, "bold")
        )
        self.subtitle_label.configure(
            bg=self.app.theme_colors["primary_bg"], 
            fg=self.app.theme_colors["text_fg"],
            font=(self.app.current_font, 10)
        )
        self.entry_key.master.configure(bg=self.app.theme_colors["primary_bg"])
        self.act_btn.configure(
            bg=self.app.theme_colors["neon_accent"], 
            activebackground=self.app.theme_colors["neon_accent"],
            font=(self.app.current_font, 11, "bold")
        )
        self.status_label.configure(
            bg=self.app.theme_colors["primary_bg"],
            font=(self.app.current_font, 10)
        )


    def activate_key(self):
        key = self.key_var.get().strip()
        if not key:
            messagebox.showwarning("Attention", "Veuillez entrer une clé.")
            return
        
        # 1. Set busy state
        self.set_buttons_active(False)
        self.app.config(cursor="watch")
        original_text = self.act_btn.cget("text")
        self.act_btn.config(text="Vérification...")
        self.set_status("Vérification en cours... (Réseau)", "#ffcc00")

        def worker_thread():
            time.sleep(0.5) 
            ok, msg, license_data = check_and_bind_key(key)
            self.app.after(0, lambda: self.handle_activation_result(ok, msg, license_data, original_text))

        threading.Thread(target=worker_thread).start()

    def handle_activation_result(self, ok, msg, license_data, original_text):
        # 1. Reset busy state
        self.set_buttons_active(True)
        self.app.config(cursor="")
        self.act_btn.config(text=original_text)
        
        if ok:
            # Succès: Sauvegarder les données et passer à la page de téléchargement
            self.app.save_license_data(license_data)
            
            if msg == "activated":
                final_msg = "Licence activée et liée à cet appareil ✅ (Données sauvegardées)"
            elif msg == "already_bound":
                final_msg = "Clé déjà activée sur cet appareil (HWID correspond)."
            else:
                final_msg = "Licence valide ✅"
            self.set_status(final_msg, self.app.theme_colors["neon_accent"])
            self.app.show_download_page(license_data)
        else:
            # Échec: Afficher l'erreur
            self.set_status(msg, "#ff4444")
            delete_local_license()


class DownloadPage(tk.Frame):
    def __init__(self, parent, app, license_data):
        super().__init__(parent, bg=app.theme_colors["primary_bg"])
        self.app = app
        self.download_link = DOWNLOAD_LINK
        self.license_data = license_data
        
        self.title_label = tk.Label(self, text="🚀 TÉLÉCHARGEMENT & LICENCE ACTIVÉE 🚀", bg=app.theme_colors["primary_bg"],
                                     fg=app.theme_colors["neon_accent"], font=(app.current_font, 18, "bold"))
        self.title_label.pack(pady=12)

        self.info_frame = tk.Frame(self, bg=app.theme_colors["primary_bg"])
        self.info_frame.pack(pady=20, padx=20, fill='x')

        self.key_label = tk.Label(self.info_frame, text="", bg=app.theme_colors["primary_bg"],
                                     fg=app.theme_colors["text_fg"], font=("Consolas", 10))
        self.key_label.pack(pady=2, anchor='w')
        self.hwid_label = tk.Label(self.info_frame, text="", bg=app.theme_colors["primary_bg"],
                                      fg=app.theme_colors["text_fg"], font=("Consolas", 10))
        self.hwid_label.pack(pady=2, anchor='w')
        self.expiry_label = tk.Label(self.info_frame, text="", bg=app.theme_colors["primary_bg"],
                                          fg=app.theme_colors["text_fg"], font=("Consolas", 10, "bold"))
        self.expiry_label.pack(pady=8, anchor='w')

        self.message_label = tk.Label(self, text="Votre licence est valide. Vous pouvez maintenant télécharger le logiciel.",
                                         bg=app.theme_colors["primary_bg"], fg=app.theme_colors["text_fg"], font=(app.current_font, 11))
        self.message_label.pack(pady=10)

        self.download_button = tk.Button(self, text="Télécharger le Logiciel",
                                             command=self.open_download_link,
                                             bg=app.theme_colors["neon_accent"],
                                             fg="#111",
                                             font=(app.current_font, 14, "bold"),
                                             width=30, borderwidth=0, relief="raised")
        self.download_button.pack(pady=15)

        self.unbind_button = tk.Button(self, text="Effacer la Licence Locale (Changer de clé)",
                                             command=self.clear_license_prompt,
                                             bg="#551111", # Rouge sombre pour l'opération de sécurité
                                             fg="#ffaaaa",
                                             font=(app.current_font, 9),
                                             width=40, borderwidth=0, relief="flat")
        self.unbind_button.pack(pady=5)
        
        self.link_label = tk.Label(self, text=f"Lien Direct : {self.download_link}",
                                      bg=app.theme_colors["primary_bg"], fg=app.theme_colors["text_fg"], font=("Consolas", 9))
        self.link_label.pack(pady=4)

        self.update_content(license_data)
        
    def clear_license_prompt(self):
        """Demande confirmation avant de supprimer la licence locale."""
        if messagebox.askyesno("Confirmation", 
                               "Êtes-vous sûr de vouloir supprimer la clé de licence de cet appareil ?\n\n"
                               "Cela vous ramènera à l'écran d'activation."):
            self.clear_license()

    def clear_license(self):
        """Supprime la licence locale et retourne à la page d'accueil."""
        if delete_local_license():
            messagebox.showinfo("Licence Effacée", "La clé de licence a été effacée de cet appareil. Veuillez réentrer une clé si vous souhaitez réutiliser le logiciel.")
            self.app.license_data = None
            self.app.pages["home"].key_var.set("") # Vide le champ d'entrée
            self.app.pages["home"].set_status("Clé locale effacée. Veuillez activer à nouveau.", self.app.theme_colors["text_fg"])
            self.app.show_home()
        else:
            messagebox.showerror("Erreur", "Impossible de supprimer le fichier de licence. Veuillez vérifier les permissions.")


    def update_theme(self):
        """Met à jour les couleurs et les polices des widgets de la page."""
        self.configure(bg=self.app.theme_colors["primary_bg"])
        self.title_label.configure(
            bg=self.app.theme_colors["primary_bg"], 
            fg=self.app.theme_colors["neon_accent"],
            font=(self.app.current_font, 18, "bold")
        )
        self.info_frame.configure(bg=self.app.theme_colors["primary_bg"])
        self.key_label.configure(bg=self.app.theme_colors["primary_bg"], fg=self.app.theme_colors["text_fg"])
        self.hwid_label.configure(bg=self.app.theme_colors["primary_bg"], fg=self.app.theme_colors["text_fg"])
        # self.expiry_label color is handled by update_content
        self.message_label.configure(
            bg=self.app.theme_colors["primary_bg"], 
            fg=self.app.theme_colors["text_fg"],
            font=(self.app.current_font, 11)
        )
        self.download_button.configure(
            bg=self.app.theme_colors["neon_accent"], 
            activebackground=self.app.theme_colors["neon_accent"],
            font=(self.app.current_font, 14, "bold")
        )
        self.unbind_button.configure(
            bg="#551111", 
            activebackground="#882222",
            font=(self.app.current_font, 9)
        )
        self.link_label.configure(bg=self.app.theme_colors["primary_bg"], fg=self.app.theme_colors["text_fg"])


    def update_content(self, license_data):
        """Met à jour les informations de licence affichées."""
        self.license_data = license_data
        if license_data:
            key_display = license_data.get('license', 'N/A')
            # Affichage partiel de la clé pour la sécurité/clarté
            masked_key = key_display[:4] + '...' + key_display[-4:]
            
            self.key_label.config(text=f"Clé: {masked_key} (Affichage partiel)")
            self.hwid_label.config(text=f"HWID Lié: {license_data.get('hwid', 'N/A')[:12]}...")
            expiry_date = license_data.get("expire", "Date non spécifiée")
            self.expiry_label.config(text=f"Expire le: {expiry_date}")
            
            if expiry_date != "Date non spécifiée" and expiry_date not in ["Lifetime", "N/A"]:
                self.expiry_label.config(fg="#ffcc00") # Jaune pour l'expiration
            elif expiry_date == "Lifetime":
                self.expiry_label.config(fg=self.app.theme_colors["neon_accent"]) # Néon pour Lifetime
            else:
                self.expiry_label.config(fg=self.app.theme_colors["text_fg"])

    def open_download_link(self):
        # Modification légère pour s'assurer que l'appel au navigateur se fait après un court délai
        # Le délai n'aide pas à fermer le navigateur, mais il aide l'OS à gérer la séquence.
        def open_browser():
            webbrowser.open(self.download_link)
            messagebox.showinfo("Téléchargement", "Le téléchargement va s'ouvrir dans votre navigateur. Veuillez utiliser la clé PRO pour décompresser l'archive si nécessaire.")

        # Lancer la commande dans le thread principal de Tkinter après un délai minimal.
        self.app.after(100, open_browser)


class OptionsPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=app.theme_colors["primary_bg"])
        self.app = app
        
        # Titre
        self.title_label = tk.Label(self, text="Options de Personnalisation", bg=app.theme_colors["primary_bg"], 
                                     fg=app.theme_colors["neon_accent"], font=(app.current_font, 16, "bold"))
        self.title_label.pack(pady=8)
        
        # --- Personnalisation des couleurs ---
        self.subtitle_colors = tk.Label(self, text="--- Thème & Couleurs ---", bg=app.theme_colors["primary_bg"],
                                             fg=app.theme_colors["text_fg"], font=(app.current_font, 11))
        self.subtitle_colors.pack(pady=5)

        # Helper function to create color buttons
        def create_color_button(text, key):
            btn = tk.Button(self, text=f"{text} ({self.app.theme_colors[key]})",
                              command=lambda: self.app.change_color(key, text),
                              bg=self.app.theme_colors["text_fg"], 
                              fg="#111", relief="flat", font=(app.current_font, 9), borderwidth=0)
            btn.pack(pady=3, padx=20, anchor="w")
            return btn

        self.btn_bg = create_color_button("Fond Principal", "primary_bg")
        self.btn_neon = create_color_button("Couleur Néon (Accent)", "neon_accent")
        self.btn_btn_bg = create_color_button("Fond Boutons Menu", "button_bg")
        self.btn_text_fg = create_color_button("Texte Secondaire", "text_fg")
        
        # --- Personnalisation de l'Apparence ---
        self.subtitle_apparence = tk.Label(self, text="--- Apparence & Police ---", bg=app.theme_colors["primary_bg"],
                                                fg=app.theme_colors["text_fg"], font=(app.current_font, 11))
        self.subtitle_apparence.pack(pady=5)
        
        # Sélecteur de police
        font_frame = tk.Frame(self, bg=app.theme_colors["primary_bg"])
        font_frame.pack(pady=5, padx=20, anchor="w")
        tk.Label(font_frame, text="Police : ", bg=app.theme_colors["primary_bg"], fg=app.theme_colors["text_fg"], font=(app.current_font, 9)).pack(side="left")
        
        self.font_var = tk.StringVar(value=app.current_font)
        
        # Utiliser un OptionMenu pour le choix des polices
        self.font_option_menu = tk.OptionMenu(font_frame, self.font_var, app.current_font, *ALT_FONTS, command=app.set_font)
        self.font_option_menu.config(bg=app.theme_colors["text_fg"], fg="#111", relief="flat", font=(app.current_font, 9), borderwidth=0)
        # Style du menu déroulant (pour le rendre dark/pro)
        self.font_option_menu["menu"].config(
            bg=app.theme_colors["button_bg"], 
            fg=app.theme_colors["text_fg"], 
            activebackground=app.theme_colors["neon_accent"], 
            activeforeground=app.theme_colors["button_bg"], 
            font=(app.current_font, 9)
        )
        self.font_option_menu.pack(side="left", padx=5)

        # --- Autres Options ---
        self.subtitle_other = tk.Label(self, text="--- Autres Fonctions PRO ---", bg=app.theme_colors["primary_bg"],
                                            fg=app.theme_colors["text_fg"], font=(app.current_font, 11))
        self.subtitle_other.pack(pady=5)
        
        # Checkbutton 
        self.var_stealth = tk.BooleanVar(value=False)
        self.check_stealth = tk.Checkbutton(self, text="Mode furtif (Cache Console/Fenêtre)", bg=app.theme_colors["primary_bg"],
                                             fg=app.theme_colors["text_fg"], selectcolor=app.theme_colors["neon_accent"],
                                             variable=self.var_stealth, font=(app.current_font, 10))
        self.check_stealth.pack(anchor="w", padx=20, pady=3)
        
        # Bouton d'action pour le démarrage automatique (exemple simple)
        self.btn_startup = tk.Button(self, text="Activer le Démarrage Automatique (Windows)", 
                                     command=lambda: messagebox.showinfo("Fonctionnalité PRO", "L'implémentation complète nécessite des droits d'admin pour modifier le Registre Windows. Cette fonction est désactivée dans cette démo."),
                                     bg=app.theme_colors["text_fg"], fg="#111", relief="flat", font=(app.current_font, 9), borderwidth=0)
        self.btn_startup.pack(anchor="w", padx=20, pady=3)
        
        self.btn_save = tk.Button(self, text="Sauvegarder les Paramètres du Thème", 
                                     command=lambda: messagebox.showinfo("OK", "Paramètres du thème sauvegardés (La persistance des thèmes doit être implémentée)."),
                                     bg=app.theme_colors["neon_accent"], fg="#111", relief="flat", font=(app.current_font, 10, "bold"), borderwidth=0)
        self.btn_save.pack(pady=10, padx=20, anchor="w")
        
        self.color_buttons = [self.btn_bg, self.btn_neon, self.btn_btn_bg, self.btn_text_fg]

    def update_theme(self):
        """Met à jour les couleurs et les polices des widgets de la page."""
        self.configure(bg=self.app.theme_colors["primary_bg"])
        
        # Labels and Titles
        self.title_label.configure(
            bg=self.app.theme_colors["primary_bg"], 
            fg=self.app.theme_colors["neon_accent"],
            font=(self.app.current_font, 16, "bold")
        )
        for sub in [self.subtitle_colors, self.subtitle_apparence, self.subtitle_other]:
            sub.configure(
                bg=self.app.theme_colors["primary_bg"], 
                fg=self.app.theme_colors["text_fg"],
                font=(self.app.current_font, 11)
            )
        
        # Checkbutton & other buttons
        self.check_stealth.configure(
            bg=self.app.theme_colors["primary_bg"], 
            fg=self.app.theme_colors["text_fg"],
            selectcolor=self.app.theme_colors["neon_accent"],
            font=(self.app.current_font, 10)
        )
        self.btn_startup.configure(
            bg=self.app.theme_colors["text_fg"], 
            activebackground=self.app.theme_colors["text_fg"],
            font=(self.app.current_font, 9)
        )
        self.btn_save.configure(
            bg=self.app.theme_colors["neon_accent"], 
            activebackground=self.app.theme_colors["neon_accent"],
            font=(self.app.current_font, 10, "bold")
        )

        # Update Color Buttons
        for btn in self.color_buttons:
            # Update button text with current color code
            text = btn.cget("text").split('(')[0].strip()
            key = [k for k, v in self.app.theme_colors.items() if v == self.app.theme_colors.get(text.split(' ')[-1]) or v == self.app.theme_colors.get(text.split(' ')[-2])] # Tricky way to re-find key based on old text
            
            # Simple manual update (less error prone for this fixed structure)
            if 'Principal' in text: btn.config(text=f"Fond Principal ({self.app.theme_colors['primary_bg']})")
            elif 'Néon' in text: btn.config(text=f"Couleur Néon (Accent) ({self.app.theme_colors['neon_accent']})")
            elif 'Menu' in text: btn.config(text=f"Fond Boutons Menu ({self.app.theme_colors['button_bg']})")
            elif 'Secondaire' in text: btn.config(text=f"Texte Secondaire ({self.app.theme_colors['text_fg']})")

            btn.configure(
                bg=self.app.theme_colors["text_fg"], 
                activebackground=self.app.theme_colors["text_fg"],
                font=(self.app.current_font, 9)
            )
            
        # Update Font Menu
        font_frame = self.font_option_menu.master
        font_frame.config(bg=self.app.theme_colors["primary_bg"])
        font_frame.winfo_children()[0].config(bg=self.app.theme_colors["primary_bg"], fg=self.app.theme_colors["text_fg"], font=(self.app.current_font, 9))

        self.font_option_menu.config(
            bg=self.app.theme_colors["text_fg"], 
            fg="#111", 
            font=(self.app.current_font, 9)
        )
        self.font_option_menu["menu"].config(
            bg=self.app.theme_colors["button_bg"], 
            fg=self.app.theme_colors["text_fg"],
            activebackground=self.app.theme_colors["neon_accent"],
            activeforeground=self.app.theme_colors["button_bg"],
            font=(self.app.current_font, 9)
        )
        self.font_var.set(self.app.current_font)


class InfoPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=app.theme_colors["primary_bg"])
        self.app = app
        
        self.title_label = tk.Label(self, text="Informations Système", bg=app.theme_colors["primary_bg"], 
                                     fg=app.theme_colors["neon_accent"], font=(app.current_font, 16, "bold"))
        self.title_label.pack(pady=8)
        
        info = f"""
        OS: {platform.system()} {platform.release()} 
        Version: {platform.version()}
        Machine: {platform.machine()}
        Processeur: {platform.processor()}
        Python: {platform.python_version()}
        HWID Complet (pour Support):
        """
        
        self.info_label = tk.Label(self, text=info, bg=app.theme_colors["primary_bg"], 
                                      fg=app.theme_colors["text_fg"], font=(app.current_font, 10), justify=tk.LEFT)
        self.info_label.pack(pady=6, padx=20, anchor='w')

        self.hwid_display = tk.Label(self, text=get_hwid(), bg="#000000", fg="#00ff00", font=("Consolas", 8), wraplength=500)
        self.hwid_display.pack(pady=2, padx=20, anchor='w')
        
        self.copy_btn = tk.Button(self, text="Copier HWID COMPLET", command=lambda: self.copy_hwid(app),
                                     bg=app.theme_colors["text_fg"], fg="#111", relief="flat", font=(app.current_font, 10), borderwidth=0)
        self.copy_btn.pack(pady=8)

    def update_theme(self):
        """Met à jour les couleurs et les polices des widgets de la page."""
        self.configure(bg=self.app.theme_colors["primary_bg"])
        self.title_label.configure(
            bg=self.app.theme_colors["primary_bg"], 
            fg=self.app.theme_colors["neon_accent"],
            font=(self.app.current_font, 16, "bold")
        )
        self.info_label.configure(
            bg=self.app.theme_colors["primary_bg"], 
            fg=self.app.theme_colors["text_fg"],
            font=(self.app.current_font, 10)
        )
        self.hwid_display.configure(
            bg="#000000",
            fg="#00ff00"
        )
        self.copy_btn.configure(
            bg=self.app.theme_colors["text_fg"], 
            activebackground=self.app.theme_colors["text_fg"],
            font=(self.app.current_font, 10)
        )

    def copy_hwid(self, app):
        try:
            app.clipboard_clear()
            app.clipboard_append(get_hwid())
            messagebox.showinfo("Copié", "HWID complet copié dans le presse-papiers.")
        except tk.TclError:
            messagebox.showerror("Erreur", "Impossible d'accéder au presse-papiers.")

class SupportPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=app.theme_colors["primary_bg"])
        self.app = app
        
        self.title_label = tk.Label(self, text="Support Technique PRO", bg=app.theme_colors["primary_bg"], 
                                     fg=app.theme_colors["neon_accent"], font=(app.current_font, 16, "bold"))
        self.title_label.pack(pady=8)
        
        self.message_label = tk.Label(self, text="Pour toute question technique ou de licence, veuillez contacter:", 
                                         bg=app.theme_colors["primary_bg"], fg=app.theme_colors["text_fg"], font=(app.current_font, 10))
        self.message_label.pack(pady=4)
        
        self.email_label = tk.Label(self, text="Email: 075pablo@gmail.com", bg=app.theme_colors["primary_bg"],
                                       fg=self.app.theme_colors["neon_accent"], font=(app.current_font, 12, "bold"))
        self.email_label.pack(pady=4)
        
        self.response_label = tk.Label(self, text="Temps de réponse PRO: 24h maximum (en général 1-2h).", bg=app.theme_colors["primary_bg"],
                                         fg=self.app.theme_colors["text_fg"], font=(app.current_font, 10))
        self.response_label.pack(pady=4)

        self.tip_label = tk.Label(self, text="\nCONSEIL: Incluez votre HWID (voir SYS INFO) dans votre email pour un traitement plus rapide.",
                                        bg=app.theme_colors["primary_bg"], fg="#ffaa00", font=(app.current_font, 9, "italic"))
        self.tip_label.pack(pady=10)

    def update_theme(self):
        """Met à jour les couleurs et les polices des widgets de la page."""
        self.configure(bg=self.app.theme_colors["primary_bg"])
        self.title_label.configure(
            bg=self.app.theme_colors["primary_bg"], 
            fg=self.app.theme_colors["neon_accent"],
            font=(self.app.current_font, 16, "bold")
        )
        self.message_label.configure(
            bg=self.app.theme_colors["primary_bg"], 
            fg=self.app.theme_colors["text_fg"],
            font=(self.app.current_font, 10)
        )
        self.email_label.configure(
            bg=self.app.theme_colors["primary_bg"], 
            fg=self.app.theme_colors["neon_accent"],
            font=(self.app.current_font, 12, "bold")
        )
        self.response_label.configure(
            bg=self.app.theme_colors["primary_bg"], 
            fg=self.app.theme_colors["text_fg"],
            font=(self.app.current_font, 10)
        )
        self.tip_label.configure(
            bg=self.app.theme_colors["primary_bg"], 
            fg="#ffaa00",
            font=(self.app.current_font, 9, "italic")
        )


# ============================
# RUN
# ============================
if __name__ == "__main__":
    # Optionnel: Cacher la console si l'application est compilée en .exe (Windows seulement)
    if platform.system() == "Windows":
        try:
            # Tente de cacher la console, seulement si elle existe
            if ctypes.windll.kernel32.GetConsoleWindow() != 0:
                ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except:
            pass # Ignorer si la console n'est pas présente ou si ctypes échoue

    app = HakoApp()
    app.mainloop()