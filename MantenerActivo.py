# -*- coding: utf-8 -*-
"""
MantenerActivo
==============
Utilidad para Windows 10/11 que evita la suspensión moviendo el ratón
de vez en cuando de forma que parece movimiento humano.

Funciones:
- Interfaz gráfica con opciones ajustables y globos de ayuda (tooltips).
- Cuenta atrás hasta la próxima interacción.
- Minimiza a la bandeja del sistema (tanto la X como minimizar la dejan
  latente ahí; se sale solo desde el menú del icono).

Dependencias para compilar/ejecutar:  pystray, pillow
(tkinter y ctypes vienen con Python).
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import ctypes
import threading
import queue
import time
import random
import math

# Bandeja del sistema (opcional: si no está, la app sigue funcionando sin ella)
try:
    import pystray
    from PIL import Image
    HAS_TRAY = True
except Exception:
    HAS_TRAY = False


def resource_path(rel):
    """Ruta a un recurso, válida tanto ejecutando el .py como el .exe (PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


# ---------------------------------------------------------------------------
# APIs de Windows (ctypes)
# ---------------------------------------------------------------------------
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Identificador propio de la app: hace que la barra de tareas use NUESTRO
# icono en vez del icono genérico del proceso anfitrión.
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        "MantenerActivo.App")
except Exception:
    pass


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def get_cursor_pos():
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def set_cursor_pos(x, y):
    user32.SetCursorPos(int(x), int(y))


def get_idle_seconds():
    """Segundos desde la última actividad del usuario (teclado o ratón)."""
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    user32.GetLastInputInfo(ctypes.byref(lii))
    return (kernel32.GetTickCount() - lii.dwTime) / 1000.0


ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


def prevent_sleep(keep_display=True):
    flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
    if keep_display:
        flags |= ES_DISPLAY_REQUIRED
    kernel32.SetThreadExecutionState(flags)


def allow_sleep():
    kernel32.SetThreadExecutionState(ES_CONTINUOUS)


# ---------------------------------------------------------------------------
# Movimiento "humano"
# ---------------------------------------------------------------------------
def ease_in_out(t):
    return 0.5 * (1 - math.cos(math.pi * t))


def human_move(dx, dy, duration):
    start_x, start_y = get_cursor_pos()
    steps = max(8, int(duration / 0.012))
    for i in range(1, steps + 1):
        t = ease_in_out(i / steps)
        jitter_x = random.uniform(-0.6, 0.6)
        jitter_y = random.uniform(-0.6, 0.6)
        x = start_x + dx * t + jitter_x
        y = start_y + dy * t + jitter_y
        set_cursor_pos(round(x), round(y))
        time.sleep(max(0.001, duration / steps + random.uniform(-0.002, 0.004)))


# ---------------------------------------------------------------------------
# Motor en segundo plano
# ---------------------------------------------------------------------------
class Jiggler:
    def __init__(self):
        self.thread = None
        self.stop_event = threading.Event()

        self.min_interval = 30.0
        self.max_interval = 60.0
        self.amplitude = 8
        self.return_to_origin = True
        self.prevent_system_sleep = True
        self.keep_display = True
        self.only_when_idle = True
        self.idle_threshold = 20.0

        self.running = False
        self.status_text = "Detenido"
        self.next_move_at = None   # time.monotonic() del próximo movimiento

    def start(self):
        if self.running:
            return
        self.stop_event.clear()
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.running = False
        self.status_text = "Detenido"
        self.next_move_at = None

    def seconds_remaining(self):
        if not self.running or self.next_move_at is None:
            return None
        return max(0, int(math.ceil(self.next_move_at - time.monotonic())))

    def _loop(self):
        try:
            if self.prevent_system_sleep:
                prevent_sleep(self.keep_display)

            while not self.stop_event.is_set():
                wait = random.uniform(self.min_interval, self.max_interval)
                self.next_move_at = time.monotonic() + wait
                self.status_text = "Activo"

                waited = 0.0
                while waited < wait and not self.stop_event.is_set():
                    step = min(0.25, wait - waited)
                    time.sleep(step)
                    waited += step
                    if self.prevent_system_sleep:
                        prevent_sleep(self.keep_display)

                if self.stop_event.is_set():
                    break

                if self.only_when_idle and get_idle_seconds() < self.idle_threshold:
                    self.status_text = "Activo (en uso, espero)"
                    continue

                self.next_move_at = None
                self.status_text = "Moviendo el ratón…"
                self._do_movement()

        finally:
            allow_sleep()

    def _do_movement(self):
        amp = max(1, int(self.amplitude))
        origin = get_cursor_pos()

        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(amp * 0.4, amp)
        dx = math.cos(angle) * dist
        dy = math.sin(angle) * dist
        human_move(dx, dy, random.uniform(0.25, 0.7))

        if random.random() < 0.5 and not self.stop_event.is_set():
            time.sleep(random.uniform(0.3, 1.0))
            human_move(random.uniform(-amp * 0.3, amp * 0.3),
                       random.uniform(-amp * 0.3, amp * 0.3),
                       random.uniform(0.15, 0.4))

        if self.return_to_origin and not self.stop_event.is_set():
            time.sleep(random.uniform(0.2, 0.8))
            cur = get_cursor_pos()
            human_move(origin[0] - cur[0], origin[1] - cur[1],
                       random.uniform(0.2, 0.5))


# ---------------------------------------------------------------------------
# Globo de ayuda (tooltip)
# ---------------------------------------------------------------------------
class Tooltip:
    def __init__(self, widget, text, delay=450, wrap=270):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.wrap = wrap
        self.tip = None
        self._after_id = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _show(self):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        lbl = tk.Label(tw, text=self.text, justify="left",
                       background="#fffce6", foreground="#1a1a1a",
                       relief="solid", borderwidth=1, wraplength=self.wrap,
                       padx=9, pady=6, font=("Segoe UI", 9))
        lbl.pack()

    def _hide(self, _=None):
        self._cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None


# Textos de ayuda de cada opción
HELP = {
    "min": "Tiempo mínimo (en segundos) que el programa espera antes de mover el "
           "ratón. La espera real de cada ciclo es aleatoria entre el mínimo y el "
           "máximo, para que el ritmo no sea predecible.",
    "max": "Tiempo máximo (en segundos) que puede esperar antes de mover el ratón. "
           "Cuanta más diferencia con el mínimo, más natural e irregular es el ritmo.",
    "amp": "Distancia máxima, en píxeles, que se desplaza el cursor en cada "
           "movimiento. Un valor pequeño (p. ej. 8) basta para evitar la suspensión "
           "sin que el ratón apenas se note.",
    "return": "Tras moverse, el cursor regresa aproximadamente al punto donde "
              "estaba. Evita que el puntero vaya 'derivando' por la pantalla con el "
              "paso del tiempo.",
    "idle": "El movimiento automático solo se realiza si llevas un rato sin tocar el "
            "teclado ni el ratón. Así el programa no interfiere mientras estás "
            "usando el equipo de verdad.",
    "idle_thr": "Segundos que debes llevar sin actividad para que el programa te "
                "considere ausente y pueda mover el ratón.",
    "sys": "Refuerzo adicional: además de mover el ratón, le pide a Windows que no "
           "suspenda el equipo (SetThreadExecutionState). Útil por si el movimiento "
           "del ratón no bastara en algún equipo.",
    "display": "Además de no suspender el equipo, impide que la pantalla se apague "
               "por inactividad.",
}


# ---------------------------------------------------------------------------
# Interfaz gráfica
# ---------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mantener Activo")
        self.resizable(False, False)
        self.jiggler = Jiggler()
        self.cmd_queue = queue.Queue()   # órdenes que llegan desde la bandeja
        self.tray = None
        self._really_quit = False

        try:
            self.iconbitmap(resource_path("raton.ico"))
        except Exception:
            pass

        self._build_ui()
        self._setup_tray()

        # Tanto la X como minimizar mandan a la bandeja
        self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)
        self.bind("<Unmap>", self._on_unmap)

        self._poll()

    # ---------------- construcción de la interfaz ----------------
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}
        main = ttk.Frame(self, padding=14)
        main.grid(row=0, column=0)

        # Estado
        self.status_var = tk.StringVar(value="Detenido")
        status_frame = ttk.Frame(main)
        status_frame.grid(row=0, column=0, columnspan=2, sticky="we")
        ttk.Label(status_frame, text="Estado:").pack(side="left")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var,
                                       font=("Segoe UI", 9, "bold"))
        self.status_label.pack(side="left", padx=6)

        # Cuenta atrás
        self.countdown_var = tk.StringVar(value="")
        self.countdown_label = ttk.Label(main, textvariable=self.countdown_var,
                                          font=("Segoe UI", 9))
        self.countdown_label.grid(row=1, column=0, columnspan=2, sticky="w",
                                  pady=(2, 8))

        # Intervalo mínimo
        lbl_min = ttk.Label(main, text="Intervalo mínimo (s):")
        lbl_min.grid(row=2, column=0, sticky="w", **pad)
        self.min_var = tk.IntVar(value=30)
        sp_min = ttk.Spinbox(main, from_=2, to=3600, textvariable=self.min_var, width=8)
        sp_min.grid(row=2, column=1, sticky="e", **pad)

        # Intervalo máximo
        lbl_max = ttk.Label(main, text="Intervalo máximo (s):")
        lbl_max.grid(row=3, column=0, sticky="w", **pad)
        self.max_var = tk.IntVar(value=60)
        sp_max = ttk.Spinbox(main, from_=2, to=7200, textvariable=self.max_var, width=8)
        sp_max.grid(row=3, column=1, sticky="e", **pad)

        # Amplitud
        lbl_amp = ttk.Label(main, text="Amplitud (píxeles):")
        lbl_amp.grid(row=4, column=0, sticky="w", **pad)
        self.amp_var = tk.IntVar(value=8)
        sp_amp = ttk.Spinbox(main, from_=1, to=200, textvariable=self.amp_var, width=8)
        sp_amp.grid(row=4, column=1, sticky="e", **pad)

        ttk.Separator(main, orient="horizontal").grid(
            row=5, column=0, columnspan=2, sticky="we", pady=8)

        # Checkboxes
        self.return_var = tk.BooleanVar(value=True)
        chk_return = ttk.Checkbutton(main, text="Volver al punto de origen tras moverse",
                                     variable=self.return_var)
        chk_return.grid(row=6, column=0, columnspan=2, sticky="w", **pad)

        self.idle_var = tk.BooleanVar(value=True)
        chk_idle = ttk.Checkbutton(main, text="Mover solo si estoy inactivo",
                                   variable=self.idle_var)
        chk_idle.grid(row=7, column=0, columnspan=2, sticky="w", **pad)

        idle_row = ttk.Frame(main)
        idle_row.grid(row=8, column=0, columnspan=2, sticky="w", padx=24)
        lbl_idle_thr = ttk.Label(idle_row, text="   Inactividad mínima (s):")
        lbl_idle_thr.pack(side="left")
        self.idle_thr_var = tk.IntVar(value=20)
        sp_idle = ttk.Spinbox(idle_row, from_=5, to=600, textvariable=self.idle_thr_var,
                              width=6)
        sp_idle.pack(side="left", padx=6)

        self.sys_var = tk.BooleanVar(value=True)
        chk_sys = ttk.Checkbutton(main, text="Evitar suspensión del sistema (refuerzo)",
                                  variable=self.sys_var)
        chk_sys.grid(row=9, column=0, columnspan=2, sticky="w", **pad)

        self.display_var = tk.BooleanVar(value=True)
        chk_display = ttk.Checkbutton(main, text="Mantener también la pantalla encendida",
                                      variable=self.display_var)
        chk_display.grid(row=10, column=0, columnspan=2, sticky="w", **pad)

        ttk.Separator(main, orient="horizontal").grid(
            row=11, column=0, columnspan=2, sticky="we", pady=8)

        self.toggle_btn = ttk.Button(main, text="▶  Activar", command=self._toggle)
        self.toggle_btn.grid(row=12, column=0, columnspan=2, sticky="we", pady=(4, 0))

        # --- Globos de ayuda (en etiqueta y control) ---
        for widgets, key in [
            ((lbl_min, sp_min), "min"),
            ((lbl_max, sp_max), "max"),
            ((lbl_amp, sp_amp), "amp"),
            ((chk_return,), "return"),
            ((chk_idle,), "idle"),
            ((lbl_idle_thr, sp_idle), "idle_thr"),
            ((chk_sys,), "sys"),
            ((chk_display,), "display"),
        ]:
            for w in widgets:
                Tooltip(w, HELP[key])

    # ---------------- bandeja del sistema ----------------
    def _setup_tray(self):
        if not HAS_TRAY:
            return
        try:
            image = Image.open(resource_path("raton.ico"))
        except Exception:
            image = Image.new("RGBA", (64, 64), (60, 60, 60, 255))

        menu = pystray.Menu(
            pystray.MenuItem("Mostrar opciones",
                             lambda i, it: self.cmd_queue.put(self._restore),
                             default=True),
            pystray.MenuItem(
                lambda it: "Desactivar" if self.jiggler.running else "Activar",
                lambda i, it: self.cmd_queue.put(self._toggle)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir",
                             lambda i, it: self.cmd_queue.put(self._real_quit)),
        )
        self.tray = pystray.Icon("MantenerActivo", image, "Mantener Activo", menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

    # ---------------- lógica ----------------
    def _apply_settings(self):
        lo = int(self.min_var.get())
        hi = int(self.max_var.get())
        if lo > hi:
            lo, hi = hi, lo
            self.min_var.set(lo)
            self.max_var.set(hi)
        j = self.jiggler
        j.min_interval = lo
        j.max_interval = hi
        j.amplitude = int(self.amp_var.get())
        j.return_to_origin = self.return_var.get()
        j.only_when_idle = self.idle_var.get()
        j.idle_threshold = int(self.idle_thr_var.get())
        j.prevent_system_sleep = self.sys_var.get()
        j.keep_display = self.display_var.get()

    def _toggle(self):
        if self.jiggler.running:
            self.jiggler.stop()
            self.toggle_btn.config(text="▶  Activar")
        else:
            try:
                self._apply_settings()
            except Exception:
                messagebox.showerror("Error", "Revisa que los valores sean números válidos.")
                return
            self.jiggler.start()
            self.toggle_btn.config(text="■  Desactivar")
        if self.tray:
            self.tray.update_menu()

    def _poll(self):
        # Atender órdenes que llegan desde la bandeja (hilo distinto)
        while not self.cmd_queue.empty():
            try:
                self.cmd_queue.get_nowait()()
            except queue.Empty:
                break
            except Exception:
                pass

        if self.jiggler.running:
            self.status_var.set(self.jiggler.status_text)
            self.status_label.config(foreground="#1a7f37")  # verde
            rem = self.jiggler.seconds_remaining()
            if "Moviendo" in self.jiggler.status_text or rem is None:
                self.countdown_var.set("Moviendo el ratón ahora…")
            else:
                self.countdown_var.set(f"Próxima interacción en {rem} s")
            self.toggle_btn.config(text="■  Desactivar")
        else:
            self.status_var.set("Detenido")
            self.status_label.config(foreground="#b42318")  # rojo
            self.countdown_var.set("")
            self.toggle_btn.config(text="▶  Activar")

        self.after(250, self._poll)

    # ---------------- bandeja / cierre ----------------
    def _on_unmap(self, event):
        # Si se minimiza desde la barra de tareas, mandar a la bandeja
        if event.widget is self and self.state() == "iconic" and HAS_TRAY:
            self._hide_to_tray()

    def _hide_to_tray(self):
        if HAS_TRAY:
            self.withdraw()
        else:
            # Sin bandeja disponible, la X cierra de verdad
            self._real_quit()

    def _restore(self):
        self.deiconify()
        self.state("normal")
        self.lift()
        self.focus_force()

    def _real_quit(self):
        self._really_quit = True
        self.jiggler.stop()
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
