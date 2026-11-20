import tkinter as tk
import numpy as np
import soundcard as sc
import threading
import random
import math
import ctypes
from ctypes import wintypes
import datetime
import time
import json
import os
import signal


# =====================================================
# Ativa DPI Real do Windows
# =====================================================

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# =====================================================
# Configurações Gerais e Memória de Posição
# =====================================================

WIDTH = 140
HEIGHT = 53

DEFAULT_X = 500
DEFAULT_Y = 300

POS_FILE = os.path.join(os.environ.get("TEMP", "."), "music_xeyes_pos.json")

def load_position():
    if os.path.exists(POS_FILE):
        try:
            with open(POS_FILE, "r") as f:
                data = json.load(f)
                return int(data.get("x", DEFAULT_X)), int(data.get("y", DEFAULT_Y))
        except Exception:
            pass
    return DEFAULT_X, DEFAULT_Y

def save_position(x, y):
    try:
        with open(POS_FILE, "w") as f:
            json.dump({"x": x, "y": y}, f)
    except Exception:
        pass

WINDOW_X, WINDOW_Y = load_position()

BACKGROUND = "#00FF00"

EYE_COLOR = "white"
PUPIL_COLOR = "#E60000"  # Vermelho

LEFT_EYE = (28, 26)
RIGHT_EYE = (74, 26)

EYE_RX = 19
EYE_RY = 11
PUPIL_RADIUS = 5

BLINK_MIN = 4000
BLINK_MAX = 7000

SAMPLE_RATE = 48000
BLOCK_SIZE = 2048

# Teclas de Atalho
LASER_KEY = 0x77     # F8 (Segurar para Laser do Ciclope)
MAG_KEY = 0x78       # F9 (Apertar para ligar/desligar Lupa de Leitura)
ESC_KEY = 0x1B       # ESC (Desliga Lupa)
PRINTSCR_KEY = 0x2C  # Print Screen
S_KEY = 0x53         # Tecla S (para detectar Win + Shift + S)
SHIFT_KEY = 0x10     # Shift
LWIN_KEY = 0x5B      # Tecla Windows Esquerda
RWIN_KEY = 0x5C      # Tecla Windows Direita

# Configurações da Lupa
MAG_SIZE = 240
MAG_ZOOM = 2.0

# Processos de gravação de tela vigiados automaticamente
RECORDER_PROCESSES = {
    "obs64.exe",
    "obs32.exe",
    "snippingtool.exe",
    "screenclippinghost.exe",
    "screenrecorder.exe",
    "gamebar.exe",
    "gamebarftserver.exe",
    "bandicam.exe",
    "camtasia.exe",
    "sharex.exe"
}


# =====================================================
# Trava de Instância Única
# =====================================================

LOCK_FILE = os.path.join(os.environ.get("TEMP", "."), "music_xeyes.pid")

if os.path.exists(LOCK_FILE):
    try:
        with open(LOCK_FILE, "r") as f:
            old_pid = int(f.read().strip())
        if old_pid != os.getpid():
            os.kill(old_pid, signal.SIGTERM)
    except Exception:
        pass

with open(LOCK_FILE, "w") as f:
    f.write(str(os.getpid()))


# =====================================================
# APIs Nativas do Windows (Captura + Detector de Processos)
# =====================================================

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC

user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int

gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC

gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP

gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ

gdi32.SetStretchBltMode.argtypes = [wintypes.HDC, ctypes.c_int]
gdi32.SetStretchBltMode.restype = ctypes.c_int

gdi32.StretchBlt.argtypes = [
    wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.DWORD
]
gdi32.StretchBlt.restype = wintypes.BOOL

gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]

HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
GA_ROOT = 2

GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020

WDA_EXCLUDEFROMCAPTURE = 0x00000011

SRCCOPY = 0x00CC0020
HALFTONE = 4
TH32CS_SNAPPROCESS = 0x00000002

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]

gdi32.GetDIBits.argtypes = [
    wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
    ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT
]
gdi32.GetDIBits.restype = ctypes.c_int

kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

def is_recorder_running():
    """Verifica nativamente se OBS, SnippingTool ou outro gravador está aberto."""
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == wintypes.HANDLE(-1).value:
        return False

    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)

    found = False
    try:
        if kernel32.Process32FirstW(snap, ctypes.byref(pe)):
            while True:
                exe_name = pe.szExeFile.lower()
                if exe_name in RECORDER_PROCESSES:
                    found = True
                    break
                if not kernel32.Process32NextW(snap, ctypes.byref(pe)):
                    break
    finally:
        kernel32.CloseHandle(snap)
    return found

def get_real_hwnd(widget):
    wid = widget.winfo_id()
    hwnd = ctypes.c_void_p(wid)
    return user32.GetAncestor(hwnd, GA_ROOT) or user32.GetParent(hwnd) or wid

def force_above_taskbar(hwnd):
    if not hwnd:
        return
    h = ctypes.c_void_p(hwnd)
    style = user32.GetWindowLongW(h, GWL_EXSTYLE)
    if not (style & WS_EX_TOPMOST):
        user32.SetWindowLongW(h, GWL_EXSTYLE, style | WS_EX_TOPMOST)
    user32.SetWindowPos(
        h, HWND_TOPMOST, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
    )

def make_click_through(hwnd):
    if not hwnd:
        return
    h = ctypes.c_void_p(hwnd)
    style = user32.GetWindowLongW(h, GWL_EXSTYLE)
    user32.SetWindowLongW(h, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)

def exclude_from_capture(hwnd):
    if not hwnd:
        return
    h = ctypes.c_void_p(hwnd)
    user32.SetWindowDisplayAffinity(h, WDA_EXCLUDEFROMCAPTURE)

def is_key_down(vk_code):
    return (user32.GetAsyncKeyState(vk_code) & 0x8000) != 0

def is_screenshot_triggered():
    if is_key_down(PRINTSCR_KEY):
        return True
    win_down = is_key_down(LWIN_KEY) or is_key_down(RWIN_KEY)
    if win_down and is_key_down(SHIFT_KEY) and is_key_down(S_KEY):
        return True
    return False

def capture_zoomed_ppm(cx, cy, size, zoom):
    src_size = max(20, int(round(size / zoom)))
    half = src_size // 2
    x = cx - half
    y = cy - half

    hdc_screen = user32.GetDC(0)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, size, size)
    old_obj = gdi32.SelectObject(hdc_mem, hbmp)

    gdi32.SetStretchBltMode(hdc_mem, HALFTONE)
    gdi32.StretchBlt(
        hdc_mem, 0, 0, size, size,
        hdc_screen, x, y, src_size, src_size,
        SRCCOPY
    )

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = size
    bmi.bmiHeader.biHeight = -size
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 24
    bmi.bmiHeader.biCompression = 0

    row_stride = ((size * 3 + 3) // 4) * 4
    buf = ctypes.create_string_buffer(row_stride * size)
    gdi32.GetDIBits(hdc_mem, hbmp, 0, size, buf, ctypes.byref(bmi), 0)

    gdi32.SelectObject(hdc_mem, old_obj)
    gdi32.DeleteObject(hbmp)
    gdi32.DeleteDC(hdc_mem)
    user32.ReleaseDC(0, hdc_screen)

    raw = np.frombuffer(buf.raw, dtype=np.uint8).reshape((size, row_stride))[:, :size * 3]
    rgb = np.ascontiguousarray(raw.reshape((size, size, 3))[:, :, ::-1])

    green_mask = (rgb[:, :, 0] == 0) & (rgb[:, :, 1] == 255) & (rgb[:, :, 2] == 0)
    rgb[green_mask, 1] = 254

    header = f"P6\n{size} {size}\n255\n".encode("ascii")
    return header + rgb.tobytes()


# =====================================================
# Monitor de Gravação em Segundo Plano
# =====================================================

recording_detected = False

def process_monitor_thread():
    global recording_detected
    while True:
        try:
            recording_detected = is_recorder_running()
        except Exception:
            recording_detected = False
        time.sleep(1.5)

def start_process_monitor():
    threading.Thread(target=process_monitor_thread, daemon=True).start()


# =====================================================
# Análise de Áudio
# =====================================================

bass_history = []
beat = False

def audio_thread():
    global beat
    try:
        speaker = sc.default_speaker()
        mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)

        with mic.recorder(samplerate=SAMPLE_RATE) as recorder:
            while True:
                data = recorder.record(numframes=BLOCK_SIZE)
                mono = np.mean(data, axis=1)
                fft = np.abs(np.fft.rfft(mono))
                freqs = np.fft.rfftfreq(len(mono), 1 / SAMPLE_RATE)

                bass = fft[(freqs > 40) & (freqs < 200)]
                level = np.mean(bass)

                bass_history.append(level)
                if len(bass_history) > 20:
                    bass_history.pop(0)

                average = np.mean(bass_history)
                if len(bass_history) > 5 and level > average * 1.0:
                    beat = True
    except Exception as e:
        print("Áudio desativado:", e)

def start_audio():
    threading.Thread(target=audio_thread, daemon=True).start()


# =====================================================
# Formatos dos Olhos (Normal e Sonolento)
# =====================================================

def get_almond_points(cx, cy, rx, ry, sleepy=False):
    top_y = cy - int(ry * 0.45) if sleepy else cy - int(ry * 1.35)
    bot_y = cy + int(ry * 1.25)
    return [
        cx - rx, cy,
        cx - rx, cy,
        cx, top_y,
        cx + rx, cy,
        cx + rx, cy,
        cx, bot_y
    ]


# =====================================================
# Janela Principal (Olhos + Acessórios)
# =====================================================

root = tk.Tk()
root.title("Music XEyes")
root.geometry(f"{WIDTH}x{HEIGHT}+{WINDOW_X}+{WINDOW_Y}")
root.overrideredirect(True)
root.attributes("-topmost", True)
root.config(bg=BACKGROUND)
root.wm_attributes("-transparentcolor", BACKGROUND)

canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg=BACKGROUND, highlightthickness=0)
canvas.pack()

root.update_idletasks()
HWND = get_real_hwnd(root)
force_above_taskbar(HWND)


# =====================================================
# Janela de Laser (Tela Cheia Transparente)
# =====================================================

SCREEN_W = root.winfo_screenwidth()
SCREEN_H = root.winfo_screenheight()

laser_win = tk.Toplevel(root)
laser_win.geometry(f"{SCREEN_W}x{SCREEN_H}+0+0")
laser_win.overrideredirect(True)
laser_win.attributes("-topmost", True)
laser_win.config(bg=BACKGROUND)
laser_win.wm_attributes("-transparentcolor", BACKGROUND)

laser_canvas = tk.Canvas(laser_win, width=SCREEN_W, height=SCREEN_H, bg=BACKGROUND, highlightthickness=0)
laser_canvas.pack()

laser_win.update_idletasks()
LASER_HWND = get_real_hwnd(laser_win)
make_click_through(LASER_HWND)
force_above_taskbar(LASER_HWND)

beam_left_glow = laser_canvas.create_line(0, 0, 0, 0, fill="#990000", width=9, capstyle="round", state="hidden")
beam_right_glow = laser_canvas.create_line(0, 0, 0, 0, fill="#990000", width=9, capstyle="round", state="hidden")
beam_left_mid = laser_canvas.create_line(0, 0, 0, 0, fill="#FF0000", width=5, capstyle="round", state="hidden")
beam_right_mid = laser_canvas.create_line(0, 0, 0, 0, fill="#FF0000", width=5, capstyle="round", state="hidden")
beam_left_core = laser_canvas.create_line(0, 0, 0, 0, fill="#FFCCCC", width=2, capstyle="round", state="hidden")
beam_right_core = laser_canvas.create_line(0, 0, 0, 0, fill="#FFCCCC", width=2, capstyle="round", state="hidden")

target_outer = laser_canvas.create_oval(0, 0, 0, 0, outline="#FF0000", width=3, state="hidden")
target_inner = laser_canvas.create_oval(0, 0, 0, 0, fill="#FFCCCC", outline="#FF0000", width=2, state="hidden")

laser_items = [
    beam_left_glow, beam_right_glow,
    beam_left_mid, beam_right_mid,
    beam_left_core, beam_right_core,
    target_outer, target_inner
]


# =====================================================
# Janela da Lupa de Leitura (Segue o Mouse)
# =====================================================

mag_win = tk.Toplevel(root)
mag_win.geometry(f"{MAG_SIZE}x{MAG_SIZE}+0+0")
mag_win.overrideredirect(True)
mag_win.attributes("-topmost", True)
mag_win.config(bg=BACKGROUND)
mag_win.wm_attributes("-transparentcolor", BACKGROUND)
mag_win.withdraw()

mag_canvas = tk.Canvas(mag_win, width=MAG_SIZE, height=MAG_SIZE, bg=BACKGROUND, highlightthickness=0)
mag_canvas.pack()

mag_win.update_idletasks()
MAG_HWND = get_real_hwnd(mag_win)
make_click_through(MAG_HWND)
exclude_from_capture(MAG_HWND)

mag_img_id = mag_canvas.create_image(0, 0, anchor="nw")
mag_mask = mag_canvas.create_oval(
    -60, -60, MAG_SIZE + 60, MAG_SIZE + 60,
    outline=BACKGROUND, width=120
)
mag_ring = mag_canvas.create_oval(
    2, 2, MAG_SIZE - 2, MAG_SIZE - 2,
    outline="#222222", width=4
)
mag_ring_inner = mag_canvas.create_oval(
    5, 5, MAG_SIZE - 5, MAG_SIZE - 5,
    outline="#4DA6FF", width=2
)
mag_photo = None


# =====================================================
# Desenho dos Olhos e Acessórios
# =====================================================

left_eye = canvas.create_polygon(
    get_almond_points(LEFT_EYE[0], LEFT_EYE[1], EYE_RX, EYE_RY),
    smooth=True, fill=EYE_COLOR, outline="black", width=2
)
right_eye = canvas.create_polygon(
    get_almond_points(RIGHT_EYE[0], RIGHT_EYE[1], EYE_RX, EYE_RY),
    smooth=True, fill=EYE_COLOR, outline="black", width=2
)

left_pupil = canvas.create_oval(0, 0, 0, 0, fill=PUPIL_COLOR, outline="black", width=1)
right_pupil = canvas.create_oval(0, 0, 0, 0, fill=PUPIL_COLOR, outline="black", width=1)

# Pálpebras (Piscar)
left_lid = canvas.create_line(
    LEFT_EYE[0]-EYE_RX, LEFT_EYE[1], LEFT_EYE[0]+EYE_RX, LEFT_EYE[1],
    fill=EYE_COLOR, width=4, state="hidden"
)
right_lid = canvas.create_line(
    RIGHT_EYE[0]-EYE_RX, RIGHT_EYE[1], RIGHT_EYE[0]+EYE_RX, RIGHT_EYE[1],
    fill=EYE_COLOR, width=4, state="hidden"
)
left_lid_border = canvas.create_line(
    LEFT_EYE[0]-EYE_RX, LEFT_EYE[1], LEFT_EYE[0]+EYE_RX, LEFT_EYE[1],
    fill="black", width=6, state="hidden"
)
right_lid_border = canvas.create_line(
    RIGHT_EYE[0]-EYE_RX, RIGHT_EYE[1], RIGHT_EYE[0]+EYE_RX, RIGHT_EYE[1],
    fill="black", width=6, state="hidden"
)
canvas.tag_lower(left_lid_border)
canvas.tag_lower(right_lid_border)

# Acessório 1: Xícara de Café (07h - 09h)
coffee_items = [
    canvas.create_oval(102, 41, 130, 46, fill="#D9D9D9", outline="black", width=1, state="hidden"),
    canvas.create_arc(121, 27, 131, 38, start=-90, extent=180, style="arc", outline="black", width=2, state="hidden"),
    canvas.create_rectangle(106, 25, 125, 42, fill="#F5F5F5", outline="black", width=1.5, state="hidden"),
    canvas.create_oval(107, 23, 124, 27, fill="#4A2511", outline="black", width=1, state="hidden"),
]
steam_1 = canvas.create_line(111, 20, 111, 12, fill="#E0E0E0", width=2, smooth=True, state="hidden")
steam_2 = canvas.create_line(119, 19, 119, 10, fill="#E0E0E0", width=2, smooth=True, state="hidden")
coffee_items.extend([steam_1, steam_2])

# Acessório 2: Óculos de Grau / Leitura (Modo Lupa)
reading_glasses_items = [
    canvas.create_oval(7, 12, 48, 40, outline="#2B2B2B", width=2.5, state="hidden"),
    canvas.create_oval(54, 12, 95, 40, outline="#2B2B2B", width=2.5, state="hidden"),
    canvas.create_line(48, 24, 54, 24, fill="#2B2B2B", width=2.5, state="hidden"),
    canvas.create_line(2, 22, 7, 23, fill="#2B2B2B", width=2.5, state="hidden"),
    canvas.create_line(95, 23, 100, 22, fill="#2B2B2B", width=2.5, state="hidden"),
]

# Acessório 3: Câmera Fotográfica (Print Screen / Win+Shift+S)
camera_items = [
    canvas.create_rectangle(104, 16, 110, 20, fill="#D0D0D0", outline="black", width=1, state="hidden"),
    canvas.create_rectangle(113, 15, 122, 20, fill="#333333", outline="black", width=1, state="hidden"),
    canvas.create_rectangle(101, 20, 132, 41, fill="#2B2B2B", outline="black", width=1.5, state="hidden"),
    canvas.create_rectangle(102, 21, 131, 26, fill="#CCCCCC", outline="", state="hidden"),
    canvas.create_oval(109, 24, 125, 40, fill="#111111", outline="#E0E0E0", width=1.5, state="hidden"),
    canvas.create_oval(113, 28, 121, 36, fill="#1E3F66", outline="#66B2FF", width=1, state="hidden"),
]
camera_flash = canvas.create_polygon(
    126, 10, 128, 16, 134, 18, 128, 20, 126, 26, 124, 20, 118, 18, 124, 16,
    fill="#FFFFCC", outline="#FFFFFF", width=1, state="hidden"
)

# Acessório 4: Filmadora de Vídeo com luz REC piscando (Gravação de Tela)
camcorder_items = [
    canvas.create_oval(102, 12, 113, 23, fill="#333333", outline="black", width=1.5, state="hidden"),
    canvas.create_oval(106, 16, 109, 19, fill="#CCCCCC", outline="", state="hidden"),
    canvas.create_oval(114, 12, 125, 23, fill="#333333", outline="black", width=1.5, state="hidden"),
    canvas.create_oval(118, 16, 121, 19, fill="#CCCCCC", outline="", state="hidden"),
    canvas.create_rectangle(102, 22, 126, 39, fill="#222222", outline="black", width=1.5, state="hidden"),
    canvas.create_polygon(126, 25, 136, 21, 136, 40, 126, 36, fill="#111111", outline="black", width=1.5, state="hidden"),
]
rec_light = canvas.create_oval(105, 25, 111, 31, fill="#FF0000", outline="#FF9999", width=1, state="hidden")


# =====================================================
# Controle de Modos, Horários, Câmera e Gravação
# =====================================================

manual_mode = "auto"
magnifier_active = False
f9_was_down = False
esc_was_down = False
print_was_down = False
camera_until = 0
flash_until = 0

def trigger_camera():
    global camera_until, flash_until
    now = time.time()
    camera_until = now + 1.6
    flash_until = now + 0.35

def get_active_mood():
    if time.time() < camera_until:
        return "camera"
    if magnifier_active:
        return "reading"
    if manual_mode != "auto":
        return manual_mode
    if recording_detected:
        return "recording"

    hour = datetime.datetime.now().hour
    if 7 <= hour < 9:
        return "coffee"
    elif hour >= 22 or hour < 6:
        return "sleepy"
    return "normal"

def apply_accessories(mood):
    for item in coffee_items:
        canvas.itemconfigure(item, state="normal" if mood == "coffee" else "hidden")
    for item in reading_glasses_items:
        canvas.itemconfigure(item, state="normal" if mood == "reading" else "hidden")
    for item in camera_items:
        canvas.itemconfigure(item, state="normal" if mood == "camera" else "hidden")
    for item in camcorder_items:
        canvas.itemconfigure(item, state="normal" if mood == "recording" else "hidden")

    if mood == "camera" and time.time() < flash_until:
        canvas.itemconfigure(camera_flash, state="normal")
    else:
        canvas.itemconfigure(camera_flash, state="hidden")

    if mood == "recording" and int(time.time() * 2) % 2 == 0:
        canvas.itemconfigure(rec_light, state="normal")
    else:
        canvas.itemconfigure(rec_light, state="hidden")

def toggle_magnifier(force_state=None):
    global magnifier_active
    if force_state is not None:
        magnifier_active = force_state
    else:
        magnifier_active = not magnifier_active

    if magnifier_active:
        mag_win.deiconify()
        mag_win.update_idletasks()
        hwnd_m = get_real_hwnd(mag_win)
        exclude_from_capture(hwnd_m)
        force_above_taskbar(hwnd_m)
    else:
        mag_win.withdraw()


# =====================================================
# Animação Principal
# =====================================================

music_jump = 0
eye_scale = 1
is_blinking = False
pulse_phase = 0
steam_phase = 0

def move_pupil(cx, cy, obj, laser_active, sleepy, posing_for_photo):
    global music_jump

    if posing_for_photo:
        px, py = cx, cy
        canvas.coords(
            obj,
            px - PUPIL_RADIUS, py - PUPIL_RADIUS,
            px + PUPIL_RADIUS, py + PUPIL_RADIUS
        )
        return (px, py)

    mx = root.winfo_pointerx() - root.winfo_rootx()
    my = root.winfo_pointery() - root.winfo_rooty()

    dx = mx - cx
    dy = (my - cy) if laser_active else (my - cy + music_jump)

    distance = math.sqrt(dx * dx + dy * dy)
    if distance > 0:
        dx /= distance
        dy /= distance

    max_x = min(distance, 9)
    max_y = min(distance, 3 if sleepy else 4)

    px = cx + dx * max_x
    py = cy + (2 if sleepy else 0) + dy * max_y

    canvas.coords(
        obj,
        px - PUPIL_RADIUS, py - PUPIL_RADIUS,
        px + PUPIL_RADIUS, py + PUPIL_RADIUS
    )
    return (px, py)


def resize_eyes(scale, sleepy):
    rx = int(EYE_RX * scale)
    ry = int(EYE_RY * scale)

    canvas.coords(left_eye, *get_almond_points(LEFT_EYE[0], LEFT_EYE[1], rx, ry, sleepy))
    canvas.coords(right_eye, *get_almond_points(RIGHT_EYE[0], RIGHT_EYE[1], rx, ry, sleepy))


def update_laser(active, l_pos, r_pos):
    global pulse_phase

    if active:
        if is_blinking:
            open_eyes(reschedule=False)

        laser_win.attributes("-topmost", True)
        laser_win.lift()
        force_above_taskbar(get_real_hwnd(laser_win))

        win_x = root.winfo_rootx()
        win_y = root.winfo_rooty()

        lx, ly = win_x + l_pos[0], win_y + l_pos[1]
        rx, ry = win_x + r_pos[0], win_y + r_pos[1]
        mx, my = root.winfo_pointerx(), root.winfo_pointery()

        for item in laser_items:
            laser_canvas.itemconfigure(item, state="normal")

        laser_canvas.coords(beam_left_glow, lx, ly, mx, my)
        laser_canvas.coords(beam_right_glow, rx, ry, mx, my)
        laser_canvas.coords(beam_left_mid, lx, ly, mx, my)
        laser_canvas.coords(beam_right_mid, rx, ry, mx, my)
        laser_canvas.coords(beam_left_core, lx, ly, mx, my)
        laser_canvas.coords(beam_right_core, rx, ry, mx, my)

        pulse_phase += 0.35
        r_outer = 14 + math.sin(pulse_phase) * 4
        r_inner = 4

        laser_canvas.coords(target_outer, mx - r_outer, my - r_outer, mx + r_outer, my + r_outer)
        laser_canvas.coords(target_inner, mx - r_inner, my - r_inner, mx + r_inner, my + r_inner)
    else:
        for item in laser_items:
            laser_canvas.itemconfigure(item, state="hidden")


def update_magnifier():
    global mag_photo
    if not magnifier_active:
        return

    mx = root.winfo_pointerx()
    my = root.winfo_pointery()

    win_x = mx - (MAG_SIZE // 2)
    win_y = my - (MAG_SIZE // 2)
    mag_win.geometry(f"{MAG_SIZE}x{MAG_SIZE}+{win_x}+{win_y}")
    mag_win.attributes("-topmost", True)
    mag_win.lift()
    force_above_taskbar(get_real_hwnd(mag_win))

    try:
        ppm_data = capture_zoomed_ppm(mx, my, MAG_SIZE, MAG_ZOOM)
        mag_photo = tk.PhotoImage(data=ppm_data, format="PPM")
        mag_canvas.itemconfigure(mag_img_id, image=mag_photo)
    except Exception:
        pass


def animation():
    global beat, music_jump, eye_scale, steam_phase
    global f9_was_down, esc_was_down, print_was_down

    print_down = is_screenshot_triggered()
    if print_down and not print_was_down:
        trigger_camera()
    print_was_down = print_down

    f9_down = is_key_down(MAG_KEY)
    if f9_down and not f9_was_down:
        toggle_magnifier()
    f9_was_down = f9_down

    esc_down = is_key_down(ESC_KEY)
    if esc_down and not esc_was_down and magnifier_active:
        toggle_magnifier(False)
    esc_was_down = esc_down

    laser_active = is_key_down(LASER_KEY)
    mood = get_active_mood()
    sleepy = (mood == "sleepy")
    posing = (mood == "camera")

    apply_accessories(mood)

    if mood == "coffee":
        steam_phase += 0.15
        offset1 = math.sin(steam_phase) * 2
        offset2 = math.cos(steam_phase) * 2
        canvas.coords(steam_1, 111, 20, 111 + offset1, 16, 111 - offset1, 11)
        canvas.coords(steam_2, 119, 19, 119 - offset2, 15, 119 + offset2, 10)

    if beat:
        music_jump = random.randint(-20, 20)
        eye_scale = 1.2
        beat = False

    music_jump *= 0.75
    eye_scale += (1.0 - eye_scale) * 0.15

    current_scale = 1.12 if (posing and time.time() < flash_until) else eye_scale
    resize_eyes(current_scale, sleepy)

    l_pos = move_pupil(*LEFT_EYE, left_pupil, laser_active, sleepy, posing)
    r_pos = move_pupil(*RIGHT_EYE, right_pupil, laser_active, sleepy, posing)

    update_laser(laser_active, l_pos, r_pos)
    update_magnifier()

    # Garante sobreposição absoluta sobre janelas maximizadas e Barra de Tarefas
    root.attributes("-topmost", True)
    root.lift()
    force_above_taskbar(get_real_hwnd(root))
    root.after(20, animation)


# =====================================================
# Piscar
# =====================================================

def blink():
    global is_blinking
    if is_key_down(LASER_KEY) or time.time() < camera_until:
        root.after(1000, blink)
        return

    is_blinking = True
    canvas.itemconfigure(left_eye, state="hidden")
    canvas.itemconfigure(right_eye, state="hidden")
    canvas.itemconfigure(left_pupil, state="hidden")
    canvas.itemconfigure(right_pupil, state="hidden")
    canvas.itemconfigure(left_lid_border, state="normal")
    canvas.itemconfigure(right_lid_border, state="normal")
    canvas.itemconfigure(left_lid, state="normal")
    canvas.itemconfigure(right_lid, state="normal")

    root.after(280, open_eyes)


def open_eyes(reschedule=True):
    global is_blinking
    is_blinking = False
    canvas.itemconfigure(left_lid, state="hidden")
    canvas.itemconfigure(right_lid, state="hidden")
    canvas.itemconfigure(left_lid_border, state="hidden")
    canvas.itemconfigure(right_lid_border, state="hidden")
    canvas.itemconfigure(left_eye, state="normal")
    canvas.itemconfigure(right_eye, state="normal")
    canvas.itemconfigure(left_pupil, state="normal")
    canvas.itemconfigure(right_pupil, state="normal")

    if reschedule:
        root.after(random.randint(BLINK_MIN, BLINK_MAX), blink)


# =====================================================
# Arrastar (Salva Posição Automaticamente) e Menu
# =====================================================

drag_x = 0
drag_y = 0

def start_drag(event):
    global drag_x, drag_y
    drag_x = event.x
    drag_y = event.y

def drag(event):
    x = root.winfo_x() + event.x - drag_x
    y = root.winfo_y() + event.y - drag_y
    root.geometry(f"+{x}+{y}")

def stop_drag(event):
    save_position(root.winfo_x(), root.winfo_y())

def reset_position():
    root.geometry(f"+{DEFAULT_X}+{DEFAULT_Y}")
    save_position(DEFAULT_X, DEFAULT_Y)

canvas.bind("<Button-1>", start_drag)
canvas.bind("<B1-Motion>", drag)
canvas.bind("<ButtonRelease-1>", stop_drag)

def set_mode(mode):
    global manual_mode
    manual_mode = mode
    if mode != "reading":
        toggle_magnifier(False)

def close_app():
    save_position(root.winfo_x(), root.winfo_y())
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass
    root.destroy()

menu = tk.Menu(root, tearoff=0)
menu.add_command(label="Lupa de Leitura (F9)", command=lambda: toggle_magnifier())
menu.add_command(label="Testar Foto (Print)", command=trigger_camera)
menu.add_separator()
menu.add_command(label="Modo Automático (Horário + Gravação)", command=lambda: set_mode("auto"))
menu.add_command(label="Visual: Normal", command=lambda: set_mode("normal"))
menu.add_command(label="Visual: Filmando (REC)", command=lambda: set_mode("recording"))
menu.add_command(label="Visual: Café da Manhã (07h-09h)", command=lambda: set_mode("coffee"))
menu.add_command(label="Visual: Sono / Cansaço (22h+)", command=lambda: set_mode("sleepy"))
menu.add_separator()
menu.add_command(label="Resetar Posição", command=reset_position)
menu.add_command(label="Fechar", command=close_app)

def popup(event):
    menu.tk_popup(event.x_root, event.y_root)

canvas.bind("<Button-3>", popup)


# =====================================================
# Iniciar
# =====================================================

start_audio()
start_process_monitor()
animation()
root.after(5000, blink)
root.mainloop()