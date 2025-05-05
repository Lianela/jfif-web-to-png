import os
import sys
# Intentar importar Image/ImageTk desde Pillow, manejar error si no está
try:
    from PIL import Image, ImageTk
except ImportError:
    print("Error: The 'Pillow' library is required but not installed.")
    print("Please install it using: pip install Pillow")
    try:
        import tkinter as tk
        from tkinter import messagebox
        root_err = tk.Tk(); root_err.withdraw()
        messagebox.showerror("Missing Library", "Pillow library is required.\n\nPlease install it:\npip install Pillow")
        root_err.destroy()
    except ImportError: pass
    sys.exit(1)

# Intentar importar CustomTkinter y tkinter base
try:
    import customtkinter as ctk
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog
except ImportError as e:
    missing_lib = "customtkinter" if "customtkinter" in str(e) else "tkinter"
    print(f"Error: The '{missing_lib}' library is required but not installed/found.")
    if missing_lib == "customtkinter": print("Please install it using: pip install customtkinter")
    try:
        if 'tk' not in locals() and 'tkinter' not in sys.modules: import tkinter as tk
        from tkinter import messagebox
        root_err = tk.Tk(); root_err.withdraw()
        messagebox.showerror("Missing Library", f"'{missing_lib}' library is required.\n\nPlease install it:\npip install {missing_lib}")
        root_err.destroy()
    except ImportError: pass
    sys.exit(1)

import platform
import threading
import time # Para pequeños delays y actualizaciones de UI
import ctypes # Para verificar y solicitar permisos de admin en Windows

# --- Constante ---
OUTPUT_FOLDER_NAME = "converted_png_images"
# Nombre del archivo de icono (debe estar en la misma carpeta que el script)
# ¡¡Asegúrate que este nombre coincida con tu archivo .ico!!
APP_ICON_FILE = "app_icon.ico" # <--- CAMBIA ESTO AL NOMBRE DE TU ICONO

# --- Funciones de Admin (Windows) ---

def is_admin():
    """ Verifica si el script se está ejecutando con privilegios de administrador en Windows """
    if platform.system() != "Windows":
        return False # Solo relevante en Windows
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """ Relanza el script actual con privilegios de administrador en Windows """
    if platform.system() != "Windows":
        print("Admin relaunch is only supported on Windows.")
        return False

    lpVerb = "runas"
    lpFile = sys.executable
    # Usar sys.argv[0] para el script principal, y el resto como parámetros
    # Esto puede ser más robusto, especialmente si el script se llama con argumentos
    # lpParameters = " ".join(sys.argv[1:]) # Pasar solo los argumentos, no el nombre del script
    # O pasar todo como antes si funciona bien
    lpParameters = " ".join(sys.argv)

    lpDirectory = os.getcwd()
    nShowCmd = 1 # SW_SHOWNORMAL

    try:
        print(f"Attempting to relaunch as admin: {lpFile} {lpParameters}")
        result = ctypes.windll.shell32.ShellExecuteW(None, lpVerb, lpFile, lpParameters, lpDirectory, nShowCmd)
        print(f"ShellExecuteW result: {result}")
        return result > 32
    except Exception as e:
        print(f"Error trying to relaunch as admin: {e}")
        # Usar tk messagebox si está disponible
        try:
            messagebox.showerror("Relaunch Error", f"Could not relaunch as administrator:\n{e}")
        except NameError: # Si messagebox no fue importado
            pass
        return False


# --- Funciones de Conversión y Escaneo (Sin cambios respecto a la versión anterior) ---
def convert_to_png(file_path, output_path_png, delete_original=False, app_instance=None):
    """ Convierte imagen, loguea a app_instance.log """
    log_func = app_instance.log if app_instance else print
    try:
        os.makedirs(os.path.dirname(output_path_png), exist_ok=True)
        if os.path.exists(output_path_png):
            # log_func(f"--- Skipped (exists): {os.path.basename(output_path_png)}", 'SKIP')
            return 'skipped'
        with Image.open(file_path) as img:
            img_to_save = img
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                 background = Image.new('RGB', img.size, (255, 255, 255))
                 try:
                     if img.mode == 'RGBA': mask = img.split()[3]
                     elif img.mode == 'LA': mask = img.split()[1]
                     elif 'transparency' in img.info:
                         img_rgba = img.convert('RGBA'); mask = img_rgba.split()[3]
                     else: mask = None
                     if mask: background.paste(img, (0, 0), mask); img_to_save = background
                     else: img_to_save = img.convert('RGB')
                 except Exception as paste_err:
                      log_func(f"*** Warn: Transparency issue {os.path.basename(file_path)}: {paste_err}", 'WARN')
                      img_to_save = img.convert('RGB')
            elif img.mode != 'RGB':
                 img_to_save = img.convert('RGB')

            img_to_save.save(output_path_png, "PNG")
            # log_func(f"-> Converted: {os.path.basename(file_path)} >> {os.path.basename(output_path_png)}", 'SUCCESS')
            if delete_original:
                try:
                    os.remove(file_path)
                    # log_func(f"--- Original deleted: {os.path.basename(file_path)}", 'WARN')
                except OSError as e:
                    log_func(f"*** Error deleting {os.path.basename(file_path)}: {e}", 'ERROR')
            return 'converted'
    except Image.UnidentifiedImageError:
        log_func(f"*** Error: Unidentified format: {os.path.basename(file_path)}", 'ERROR')
        return 'error'
    except PermissionError:
        log_func(f"*** Error: Permission denied saving {os.path.basename(output_path_png)}", 'ERROR')
        return 'error'
    except Exception as e:
        log_func(f"*** Error converting {os.path.basename(file_path)}: {e}", 'ERROR')
        return 'error'

def scan_and_convert(root_directory, output_base_folder, delete_originals=False, app_instance=None):
    """ Escanea y convierte, actualizando UI con más detalle """
    log_func = app_instance.log
    update_progress = app_instance.update_progress_and_label
    update_status = app_instance.update_status_label
    update_ui = app_instance.after

    log_func(f"\nStarting scan in: {root_directory}", 'INFO')
    log_func(f"Output folder: {output_base_folder}", 'INFO')
    if delete_originals: log_func("Delete originals option is ON.", 'WARN')

    counter = {'converted': 0, 'skipped': 0, 'error': 0, 'processed': 0}
    extensions_to_find = (".webp", ".jfif", ".jif"); files_to_process = []
    permission_errors_count = 0

    # --- Primera pasada: Contar archivos y carpetas ---
    update_status("Counting files...")
    update_ui(1, lambda: None) # Forzar update inicial
    processed_folders = 0
    start_time_count = time.time()
    try:
        def onerror_handler(err):
            nonlocal permission_errors_count
            if isinstance(err, OSError):
                permission_errors_count += 1
                if permission_errors_count <= 10: log_func(f"--- Permission error accessing: {os.path.basename(err.filename)}", 'SKIP')
                elif permission_errors_count == 11: log_func("--- (Further permission errors omitted)", 'SKIP')
            else: log_func(f"*** OS Walk Error: {err} ***", 'ERROR')

        for current_folder, _, files in os.walk(root_directory, topdown=True, onerror=onerror_handler):
             if app_instance and app_instance.stop_scan_flag.is_set():
                 log_func("Scan stopped during counting.", "WARN"); return
             processed_folders += 1
             if processed_folders % 100 == 0:
                 update_status(f"Counting... (Folder: ...{os.path.basename(current_folder)})")
                 update_ui(1, lambda: None) # Permitir que la UI respire

             for filename in files:
                  if filename.lower().endswith(extensions_to_find):
                       files_to_process.append(os.path.join(current_folder, filename))

        if permission_errors_count > 0: log_func(f"--- Skipped {permission_errors_count} directories due to permissions.", 'SKIP')

    except Exception as e:
        log_func(f"\n*** Error counting files: {e} ***", 'ERROR')
        app_instance.show_message("Scan Error", f"Error counting files:\n{e}", error=True); return
    finally: update_status("")

    count_time = time.time() - start_time_count
    total_files = len(files_to_process)
    log_func(f"Count finished in {count_time:.2f}s. Found {total_files} files.", 'INFO')
    update_progress(0, total_files); update_ui(1, lambda: None)

    if total_files == 0:
         log_func("No matching files found.", 'INFO')
         app_instance.show_message("Scan Complete", "No matching files found.", info=True); return

    # --- Segunda pasada: Procesar archivos ---
    update_status("Converting images...")
    start_time_convert = time.time()
    try:
        for i, original_full_path in enumerate(files_to_process):
             if app_instance and app_instance.stop_scan_flag.is_set():
                 log_func("Scan stopped during conversion.", "WARN"); break

             counter['processed'] = i + 1
             update_progress(counter['processed'], total_files)
             if counter['processed'] % 20 == 0 or counter['processed'] == total_files: update_ui(1, lambda: None)

             result = convert_to_png(original_full_path,
                                     os.path.join(output_base_folder, os.path.basename(original_full_path).rsplit('.', 1)[0] + ".png"),
                                     delete_originals, app_instance=app_instance)
             if result in counter: counter[result] += 1
    except Exception as e:
         log_func(f"\n*** Error during conversion: {e} ***", 'ERROR')
         log_func("*** Scan may be incomplete. ***", 'ERROR')
         app_instance.show_message("Scan Error", f"Error during conversion:\n{e}", error=True)
    finally: update_status("")

    convert_time = time.time() - start_time_convert
    update_ui(1, lambda: None)
    # --- Resumen Final ---
    if not (app_instance and app_instance.stop_scan_flag.is_set()):
        summary = (f"\n--- Scan Finished ({convert_time:.2f}s) ---\n"
                   f"Processed: {counter['processed']} | Converted: {counter['converted']} | Skipped: {counter['skipped']} | Errors: {counter['error']}\n")
        summary += f"Output: {output_base_folder}\n"
        summary += "Originals " + ("deleted." if delete_originals else "kept.")
        log_func(summary, 'INFO'); app_instance.show_message("Scan Complete", summary.strip(), info=True)


# --- GUI Application Class (CustomTkinter) ---

class ImageConverterApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Image Converter")
        self.geometry("800x650")
        self.minsize(700, 600)

        # --- Colores ---
        self.DARK_BG = '#2b2b2b'; self.DARK_BG_FRAME = '#383838'; self.DARK_FG = '#dcdcdc'
        self.DARK_FG_DISABLED = '#888888'; self.DARK_SELECT_BG = '#4f4f4f'; self.ACCENT_COLOR = '#0078d4'
        self.DARK_BUTTON = '#4a4a4a'; self.DARK_BUTTON_ACCENT = '#005a9e'; self.ERROR_COLOR = '#f44336'
        self.WARN_COLOR = '#ff9800'; self.SUCCESS_COLOR = '#4CAF50'; self.SKIP_COLOR = '#aaaaaa'
        self.DARK_ENTRY_BG = '#3c3c3c'; self.DARK_BORDER = '#555555'
        self.ADMIN_COLOR = self.WARN_COLOR

        # --- Configurar tema y apariencia ---
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # --- Variables ---
        self.scan_option = tk.StringVar(value="current")
        self.specific_dir = tk.StringVar(value="")
        self.delete_originals_var = tk.BooleanVar(value=False)
        try:
            if getattr(sys, 'frozen', False): self.script_dir = os.path.dirname(sys.executable)
            else: self.script_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError: self.script_dir = os.getcwd()
        self.output_folder_path = os.path.join(self.script_dir, OUTPUT_FOLDER_NAME)
        self.is_currently_admin = is_admin()

        # --- Establecer Icono de Ventana ---
        self.setup_window_icon() # Llamar a la nueva función

        # --- Cargar Iconos para Botones ---
        self.icons = {}
        self.load_button_icons() # Llamar a la nueva función

        # --- Layout Principal (Grid) ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # Frame opciones
        self.grid_rowconfigure(1, weight=0) # Frame delete y output
        self.grid_rowconfigure(2, weight=1) # Frame log (expandir)
        self.grid_rowconfigure(3, weight=0) # Frame acciones (botón/progreso/status)
        self.grid_rowconfigure(4, weight=0) # Frame admin status (nueva fila)

        # --- Frame Opciones ---
        options_frame = ctk.CTkFrame(self, corner_radius=10)
        options_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        options_frame.grid_columnconfigure(1, weight=1)
        options_label = ctk.CTkLabel(options_frame, text="1. Select Scan Location", font=ctk.CTkFont(size=14, weight="bold"))
        options_label.grid(row=0, column=0, columnspan=2, padx=15, pady=(10, 15), sticky="w")
        self.rb_current = ctk.CTkRadioButton(options_frame, text=f"Current Directory ({os.path.basename(self.script_dir)})",
                                             variable=self.scan_option, value="current", command=self.update_ui_state)
        self.rb_current.grid(row=1, column=0, columnspan=2, padx=20, pady=5, sticky="w")
        self.rb_specific = ctk.CTkRadioButton(options_frame, text="Specific Directory:",
                                              variable=self.scan_option, value="specific", command=self.update_ui_state)
        self.rb_specific.grid(row=2, column=0, padx=(20, 5), pady=5, sticky="w")
        specific_dir_subframe = ctk.CTkFrame(options_frame, fg_color="transparent")
        specific_dir_subframe.grid(row=2, column=1, padx=(0, 15), pady=0, sticky="ew")
        specific_dir_subframe.grid_columnconfigure(0, weight=1)
        self.specific_dir_entry = ctk.CTkEntry(specific_dir_subframe, textvariable=self.specific_dir,
                                               placeholder_text="Path to directory...", state=tk.DISABLED, corner_radius=8)
        self.specific_dir_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.browse_button = ctk.CTkButton(specific_dir_subframe, text="Browse", width=85,
                                           image=self.icons.get("browse"), compound="left",
                                           command=self.browse_directory, state=tk.DISABLED, corner_radius=8)
        self.browse_button.grid(row=0, column=1, sticky="w")
        self.rb_full = ctk.CTkRadioButton(options_frame, text="Full System/Drive (Requires Admin)",
                                          variable=self.scan_option, value="full", command=self.update_ui_state)
        self.rb_full.grid(row=3, column=0, columnspan=2, padx=20, pady=(5, 10), sticky="w")

        # --- Frame Opciones Adicionales ---
        extra_options_frame = ctk.CTkFrame(self, fg_color="transparent")
        extra_options_frame.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        extra_options_frame.columnconfigure(1, weight=1)
        delete_label = ctk.CTkLabel(extra_options_frame, text="2. Options", font=ctk.CTkFont(size=14, weight="bold"))
        delete_label.grid(row=0, column=0, columnspan=2, padx=0, pady=(10, 5), sticky="w")
        self.delete_check = ctk.CTkCheckBox(extra_options_frame, text="Delete original files after conversion",
                                            variable=self.delete_originals_var, checkbox_width=18, checkbox_height=18, corner_radius=5)
        self.delete_check.grid(row=1, column=0, columnspan=2, padx=0, pady=5, sticky="w")
        output_label = ctk.CTkLabel(extra_options_frame, text="Output Folder:", anchor="w")
        output_label.grid(row=2, column=0, padx=0, pady=(5, 10), sticky="w")
        self.output_path_label = ctk.CTkLabel(extra_options_frame, text=self.output_folder_path, anchor="w", text_color=self.SKIP_COLOR, font=ctk.CTkFont(size=11))
        self.output_path_label.grid(row=2, column=1, padx=5, pady=(5, 10), sticky="ew")

        # --- Frame Log ---
        log_frame = ctk.CTkFrame(self, corner_radius=10)
        log_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        log_frame.grid_rowconfigure(1, weight=1); log_frame.grid_columnconfigure(0, weight=1)
        log_label = ctk.CTkLabel(log_frame, text="Log Output", font=ctk.CTkFont(weight="bold"))
        log_label.grid(row=0, column=0, padx=15, pady=(10, 5), sticky="w")
        self.log_textbox = ctk.CTkTextbox(log_frame, wrap=tk.WORD, corner_radius=8, border_width=1,
                                          font=ctk.CTkFont(family="Consolas", size=11), activate_scrollbars=True)
        self.log_textbox.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")
        self.log_textbox.configure(state="disabled")
        info_fg_color = self.DARK_FG if ctk.get_appearance_mode() == "Dark" else "#000000"
        self.log_textbox.tag_config("INFO", foreground=info_fg_color)
        self.log_textbox.tag_config("ERROR", foreground=self.ERROR_COLOR)
        self.log_textbox.tag_config("WARN", foreground=self.WARN_COLOR)
        self.log_textbox.tag_config("SUCCESS", foreground=self.SUCCESS_COLOR)
        self.log_textbox.tag_config("SKIP", foreground=self.SKIP_COLOR)

        # --- Frame Acciones ---
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.grid(row=3, column=0, padx=20, pady=(10, 5), sticky="ew")
        action_frame.grid_columnconfigure(0, weight=1)
        button_subframe = ctk.CTkFrame(action_frame, fg_color="transparent")
        button_subframe.grid(row=0, column=0, pady=(0, 10))
        self.start_button = ctk.CTkButton(button_subframe, text="Start Scan", image=self.icons.get("start"), compound="left",
                                          command=self.start_scan_thread, height=40,
                                          font=ctk.CTkFont(size=13, weight="bold"), corner_radius=8)
        self.start_button.grid(row=0, column=0, padx=10)
        self.stop_button = ctk.CTkButton(button_subframe, text="Stop Scan", image=self.icons.get("stop"), compound="left",
                                         command=self.stop_scan, height=40,
                                         font=ctk.CTkFont(size=13, weight="bold"), corner_radius=8,
                                         fg_color=self.WARN_COLOR, hover_color="#cc7a00", state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=10)
        progress_status_frame = ctk.CTkFrame(action_frame, fg_color="transparent")
        progress_status_frame.grid(row=1, column=0, sticky="ew", pady=(5,0))
        progress_status_frame.grid_columnconfigure(0, weight=1)
        progress_status_frame.grid_columnconfigure(1, weight=0)
        self.status_label = ctk.CTkLabel(progress_status_frame, text="", anchor="w", font=ctk.CTkFont(size=11), text_color=self.SKIP_COLOR)
        self.status_label.grid(row=0, column=0, padx=(5, 10), sticky="ew")
        self.progress_bar = ctk.CTkProgressBar(progress_status_frame, orientation="horizontal", height=10, corner_radius=5, width=200)
        self.progress_bar.grid(row=0, column=1, sticky="e")
        self.progress_bar.set(0)

        # --- Frame Admin Status ---
        admin_frame = ctk.CTkFrame(self, fg_color="transparent")
        admin_frame.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="e")
        admin_text = "Administrator Privileges: Active" if self.is_currently_admin else "Standard User Privileges"
        admin_color = self.ADMIN_COLOR if self.is_currently_admin else self.SKIP_COLOR
        admin_icon = self.icons.get("shield") if self.is_currently_admin else None
        self.admin_status_label = ctk.CTkLabel(admin_frame, text=admin_text, image=admin_icon, compound="left",
                                               font=ctk.CTkFont(size=10), text_color=admin_color)
        self.admin_status_label.pack()

        # --- Inicialización Final ---
        self.log(f"Script location: {self.script_dir}", 'INFO')
        self.log(f"Output folder: {self.output_folder_path}", 'INFO')
        self.log(f"Running with: {admin_text}", 'INFO')
        self.log("Select scan location and press 'Start Scan'.", 'INFO')
        self.update_ui_state()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.scan_thread = None
        self.stop_scan_flag = threading.Event()

    # --- Métodos de la GUI (adaptados a CTk y UX) ---

    def setup_window_icon(self):
        """ Establece el icono de la ventana principal si el archivo .ico existe """
        icon_path = os.path.join(self.script_dir, APP_ICON_FILE)
        if os.path.exists(icon_path):
            try:
                # self.iconbitmap() es un método de la ventana raíz (CTk)
                self.iconbitmap(icon_path)
                print(f"Window icon set from: {icon_path}")
            except Exception as e:
                print(f"Warning: Could not set window icon from {icon_path}: {e}")
        else:
            print(f"Warning: Window icon file not found: {icon_path}")

    def load_button_icons(self):
        """ Carga los iconos para los botones """
        icon_size = (18, 18)
        icon_files = {"browse": "browse_icon.png", "start": "start_icon.png", "stop": "stop_icon.png", "shield": "shield_icon.png"}
        for name, filename in icon_files.items():
            try:
                icon_path = os.path.join(self.script_dir, filename)
                if os.path.exists(icon_path):
                    img = Image.open(icon_path).resize(icon_size)
                    self.icons[name] = ImageTk.PhotoImage(img)
                else: print(f"Warning: Button icon file not found: {filename}")
            except Exception as e: print(f"Warning: Could not load button icon {filename}: {e}")

    def center_window(self, width=800, height=650):
        """ Centra la ventana en la pantalla """
        try:
            self.update_idletasks(); screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight(); center_x = max(0, int(screen_width/2 - width / 2))
            center_y = max(0, int(screen_height/2 - height / 2))
            self.geometry(f'{width}x{height}+{center_x}+{center_y}')
        except Exception as e: print(f"Could not center window: {e}"); self.geometry(f"{width}x{height}")

    def log(self, message, tag='INFO'):
        """ Añade mensaje al CTkTextbox (thread-safe) """
        tag_upper = tag.upper(); self.after(0, self._insert_log, message, tag_upper)

    def _insert_log(self, message, tag):
        """ Método interno para insertar en el log """
        try:
            if self.log_textbox.winfo_exists():
                self.log_textbox.configure(state="normal")
                color_map = {'INFO': getattr(self, 'DARK_FG', '#dcdcdc') if ctk.get_appearance_mode() == "Dark" else "#000000",
                             'ERROR': getattr(self, 'ERROR_COLOR', '#ff0000'), 'WARN': getattr(self, 'WARN_COLOR', '#ffa500'),
                             'SUCCESS': getattr(self, 'SUCCESS_COLOR', '#008000'), 'SKIP': getattr(self, 'SKIP_COLOR', '#808080')}
                if tag not in self.log_textbox.tag_names():
                    try:
                        fg_color = color_map.get(tag, color_map['INFO'])
                        self.log_textbox.tag_config(tag, foreground=fg_color)
                    except Exception as tag_ex: print(f"Error configuring tag {tag}: {tag_ex}"); tag = 'INFO'
                self.log_textbox.insert(tk.END, message + "\n", tag)
                self.log_textbox.configure(state="disabled")
                self.log_textbox.see(tk.END)
        except Exception as e: print(f"Log error: {e}")

    def update_progress_and_label(self, value, maximum):
        """ Actualiza barra y etiqueta de progreso (thread-safe) """
        self.after(0, self._update_progress_and_label, value, maximum)

    def _update_progress_and_label(self, value, maximum):
        """ Método interno para actualizar progreso y etiqueta """
        try:
            progress_float = 0.0; status_text = ""
            if maximum > 0:
                progress_float = max(0.0, min(1.0, float(value) / maximum))
                if value % 20 == 0 or value == maximum or value == 1:
                     status_text = f"Processing: {value} / {maximum}"
                     if self.status_label.winfo_exists(): self.status_label.configure(text=status_text)
            else:
                status_text = "Processing: 0 / 0"
                if self.status_label.winfo_exists(): self.status_label.configure(text=status_text)
            if self.progress_bar.winfo_exists(): self.progress_bar.set(progress_float)
        except Exception as e: print(f"Progress update error: {e}")

    def update_status_label(self, text):
         """ Actualiza solo la etiqueta de estado (thread-safe) """
         self.after(0, self._update_status_label, text)

    def _update_status_label(self, text):
        """ Método interno para actualizar etiqueta de estado """
        try:
             if self.status_label.winfo_exists(): self.status_label.configure(text=text)
        except Exception as e: print(f"Status label update error: {e}")

    def show_message(self, title, message, info=False, error=False, warning=False):
         """ Muestra un messagebox estándar (thread-safe) """
         self.after(0, self._show_message, title, message, info, error, warning)

    def _show_message(self, title, message, info, error, warning):
          """ Método interno para mostrar messagebox """
          try:
              if self.winfo_exists():
                  if error: messagebox.showerror(title, message, parent=self)
                  elif warning: messagebox.showwarning(title, message, parent=self)
                  else: messagebox.showinfo(title, message, parent=self)
          except Exception as e: print(f"Messagebox error: {e}")

    def update_ui_state(self, scanning=False):
        """ Habilita/deshabilita widgets basado en la selección y estado de escaneo """
        try:
            scan_controls_state = tk.DISABLED if scanning else tk.NORMAL
            start_button_state = tk.DISABLED if scanning else tk.NORMAL
            stop_button_state = tk.NORMAL if scanning else tk.DISABLED

            if hasattr(self, 'rb_current'): self.rb_current.configure(state=scan_controls_state)
            if hasattr(self, 'rb_specific'): self.rb_specific.configure(state=scan_controls_state)
            if hasattr(self, 'rb_full'): self.rb_full.configure(state=scan_controls_state)
            if hasattr(self, 'delete_check'): self.delete_check.configure(state=scan_controls_state)

            is_specific_selected = self.scan_option.get() == "specific" and not scanning
            if hasattr(self, 'specific_dir_entry'): self.specific_dir_entry.configure(state=tk.NORMAL if is_specific_selected else tk.DISABLED)
            if hasattr(self, 'browse_button'): self.browse_button.configure(state=tk.NORMAL if is_specific_selected else tk.DISABLED)

            if hasattr(self, 'start_button'): self.start_button.configure(state=start_button_state)
            if hasattr(self, 'stop_button'): self.stop_button.configure(state=stop_button_state)

        except Exception as e: print(f"Error updating UI state: {e}")

    def browse_directory(self):
        """ Abre el diálogo para seleccionar carpeta """
        directory = filedialog.askdirectory(title="Select Directory to Scan")
        if directory: self.specific_dir.set(directory); self.log(f"Selected specific directory: {directory}", 'INFO')

    def get_scan_path(self):
        """ Determina la ruta a escanear, manejando la solicitud de admin """
        option = self.scan_option.get(); scan_path = None
        if option == "current": scan_path = self.script_dir; self.log(f"Scan target: Current directory ({scan_path})", 'INFO')
        elif option == "specific":
            scan_path = self.specific_dir.get()
            if not scan_path: self.show_message("Input Error", "Please select a specific directory.", error=True); return None
            if not os.path.isdir(scan_path): self.show_message("Error", f"Invalid directory:\n'{scan_path}'", error=True); return None
            self.log(f"Scan target: Specific directory ({scan_path})", 'INFO')
        elif option == "full":
            if platform.system() == "Windows":
                if not self.is_currently_admin:
                    self.log("Admin privileges needed for full scan.", "WARN")
                    if messagebox.askyesno("Admin Privileges Required",
                                           "Scanning the entire system requires administrator privileges.\n"
                                           "The application needs to restart with elevated rights.\n\n"
                                           "Do you want to restart as administrator now?",
                                           icon='warning', parent=self):
                        if run_as_admin():
                            self.log("Relaunching as administrator...", "INFO")
                            self.destroy(); return None
                        else:
                            self.log("Failed to relaunch as administrator.", "ERROR")
                            self.show_message("Error", "Could not restart with administrator privileges.", error=True); return None
                    else:
                        self.log("Admin privileges denied by user.", "INFO")
                        self.scan_option.set("current"); self.update_ui_state(); return None
                dialog = ctk.CTkInputDialog(text="Enter drive letter (e.g., C):", title="Full System Scan")
                drive_letter = dialog.get_input()
                if drive_letter:
                    drive_letter = drive_letter.strip().upper()
                    if len(drive_letter) == 1 and 'A' <= drive_letter <= 'Z':
                         root_dir = f"{drive_letter}:\\"
                         if not os.path.isdir(root_dir): self.show_message("Error", f"Drive {root_dir} not accessible.", error=True); root_dir = None
                         else: scan_path = root_dir
                    else: self.show_message("Error", "Invalid drive letter.", error=True)
                else: return None
                if scan_path: self.log(f"Scan target: Full scan ({scan_path})", 'WARN')
            elif platform.system() in ["Linux", "Darwin"]:
                 root_dir = "/"
                 warning_msg = (f"!!! WARNING: Scanning entire system ({root_dir}) !!!\n\n"
                                f"- VERY slow.\n- Requires read permissions everywhere.\n"
                                f"- Output in '{os.path.basename(self.output_folder_path)}'.\n\nProceed?")
                 if messagebox.askyesno("Confirm Full Scan", warning_msg, icon='warning', parent=self):
                     scan_path = root_dir; self.log(f"Scan target: Full scan ({scan_path})", 'WARN')
                 else: self.log("Full system scan cancelled.", 'INFO'); return None
            else: self.show_message("Error", f"Unsupported OS ({os_name}).", error=True); return None
        return scan_path

    def start_scan_thread(self):
        """ Inicia el escaneo en un hilo separado """
        if self.scan_thread and self.scan_thread.is_alive():
             self.show_message("Info", "Scan already in progress.", info=True); return
        scan_path = self.get_scan_path()
        if not scan_path: return

        delete = self.delete_originals_var.get(); delete_confirmed = delete
        if delete:
            if not messagebox.askyesno("Confirm Deletion", f"ATTENTION! Delete original files in:\n'{scan_path}'?\n\nCANNOT BE UNDONE. Sure?", icon='warning', parent=self):
                self.log("Deletion cancelled.", 'INFO'); delete_confirmed = False
            else: self.log("Deletion confirmed.", 'WARN')

        self.update_ui_state(scanning=True)
        self.progress_bar.set(0)
        self.status_label.configure(text="Starting...")
        self.log("Starting scan process...", 'INFO')
        self.stop_scan_flag.clear()
        self.scan_thread = threading.Thread(target=self.run_scan, args=(scan_path, self.output_folder_path, delete_confirmed), daemon=True)
        self.scan_thread.start()

    def stop_scan(self):
        """ Activa el flag para detener el escaneo en curso """
        if self.scan_thread and self.scan_thread.is_alive():
            self.log("Attempting to stop scan...", "WARN")
            self.update_status_label("Stopping...")
            self.stop_scan_flag.set()
            self.stop_button.configure(state=tk.DISABLED)
        else:
            self.log("No scan is currently running.", "INFO")

    def run_scan(self, scan_path, output_folder, delete_confirmed):
        """ Función que se ejecuta en el hilo para realizar el escaneo """
        try: scan_and_convert(scan_path, output_folder, delete_confirmed, app_instance=self)
        except Exception as e:
            self.log(f"\n\n*** THREAD ERROR: {e} ***", 'ERROR'); import traceback; self.log(traceback.format_exc(), 'ERROR')
            self.show_message("Fatal Error", f"Unexpected scan error. Check log.", error=True)
        finally:
            self.after(0, self.scan_finished_ui_update)
            self.scan_thread = None

    def scan_finished_ui_update(self):
        """ Actualiza la UI cuando el escaneo termina o se detiene """
        self.update_ui_state(scanning=False)
        if not self.stop_scan_flag.is_set(): self.status_label.configure(text="Finished.")
        else: self.status_label.configure(text="Stopped by user.")

    def on_closing(self):
        """ Maneja el cierre de la ventana """
        if self.scan_thread and self.scan_thread.is_alive():
             if messagebox.askyesno("Exit Confirmation", "Scan in progress. Exit anyway?", icon='warning', parent=self):
                 self.stop_scan_flag.set()
                 self.after(100, self.destroy)
        else:
             self.destroy()

# --- Punto de Entrada ---
if __name__ == "__main__":
    # Comprobaciones iniciales
    try: from PIL import Image, ImageTk
    except ImportError: print("CRITICAL ERROR: Pillow library not found."); sys.exit(1)
    try: import customtkinter
    except ImportError: print("CRITICAL ERROR: CustomTkinter library not found."); sys.exit(1)

    # Iniciar la aplicación CustomTkinter
    app = ImageConverterApp()
    app.mainloop()
