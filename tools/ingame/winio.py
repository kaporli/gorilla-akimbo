"""Windows side of the harness: processes, game window, input, screenshots and recordings (ctypes and ffmpeg only)."""
import ctypes, ctypes.wintypes as wt, subprocess, time

u32 = ctypes.windll.user32
FFMPEG = 'C:/Modding/_tools/ffmpeg/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe'
TITLE = 'Cyberpunk 2077'


def running(image):
    out = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {image}', '/FO', 'CSV', '/NH'], capture_output=True, text=True).stdout
    return image.lower() in out.lower()


def kill(image, force=False):
    """Close by name; without force the process gets a normal close request."""
    subprocess.run(['taskkill', '/IM', image] + (['/F'] if force else []), capture_output=True)


def wait_gone(image, timeout):
    t = time.time()
    while time.time() - t < timeout:
        if not running(image): return True
        time.sleep(1)
    return not running(image)


def monitors():
    return u32.GetSystemMetrics(80)


def window(title=TITLE):
    """(hwnd, (x, y, w, h)) of the visible game window, or None."""
    found = []
    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _):
        if u32.IsWindowVisible(h):
            n = u32.GetWindowTextLengthW(h)
            b = ctypes.create_unicode_buffer(n + 1)
            u32.GetWindowTextW(h, b, n + 1)
            if b.value.startswith(title) and 'Mod Organizer' not in b.value:
                found.append(h)
        return True
    u32.EnumWindows(cb, 0)
    if not found: return None
    r = wt.RECT()
    u32.GetWindowRect(found[0], ctypes.byref(r))
    return found[0], (r.left, r.top, r.right - r.left, r.bottom - r.top)


def front():
    w = window()
    if w: u32.ShowWindow(w[0], 9); u32.SetForegroundWindow(w[0])
    return w


class _MI(ctypes.Structure):
    _fields_ = [('dx', wt.LONG), ('dy', wt.LONG), ('d', wt.DWORD), ('f', wt.DWORD), ('t', wt.DWORD), ('x', ctypes.c_size_t)]


class _KI(ctypes.Structure):
    _fields_ = [('vk', wt.WORD), ('sc', wt.WORD), ('f', wt.DWORD), ('t', wt.DWORD), ('x', ctypes.c_size_t)]


class _U(ctypes.Union):
    _fields_ = [('mi', _MI), ('ki', _KI)]


class _IN(ctypes.Structure):
    _fields_ = [('type', wt.DWORD), ('u', _U)]


VK = {'SPACE': 0x20, 'ESC': 0x1B, 'ENTER': 0x0D, 'TAB': 0x09, 'UP': 0x26, 'DOWN': 0x28, 'LEFT': 0x25, 'RIGHT': 0x27,
      'R': 0x52, 'V': 0x56, 'C': 0x43, 'F': 0x46, 'E': 0x45, 'W': 0x57, 'A': 0x41, 'S': 0x53, 'D': 0x44}
VK.update({f'D{i}': 0x30 + i for i in range(10)})
VK.update({f'F{i}': 0x6F + i for i in range(1, 13)})
MB = {'LMB': (2, 4), 'RMB': (8, 16), 'MMB': (32, 64)}


def _send(i):
    u32.SendInput(1, ctypes.byref(i), ctypes.sizeof(_IN))


def key(name, hold_ms=60):
    """Press a key (never Alt: refused)."""
    if name.upper() in ('ALT', 'MENU'): raise ValueError('Alt is never pressed')
    vk = VK[name.upper()]
    sc = u32.MapVirtualKeyW(vk, 0)
    for up in (0, 2):
        i = _IN(1); i.u.ki = _KI(0, sc, 8 | up, 0, 0)
        _send(i)
        if not up: time.sleep(hold_ms / 1000)


def mouse(button, hold_ms=60):
    d, u = MB[button.upper()]
    for fl in (d, u):
        i = _IN(0); i.u.mi = _MI(0, 0, 0, fl, 0, 0)
        _send(i)
        if fl == d: time.sleep(hold_ms / 1000)


def click(x, y):
    u32.SetCursorPos(int(x), int(y))
    time.sleep(0.1)
    mouse('LMB', 80)


def _grab(w, extra):
    x, y, ww, hh = w[1]
    return [FFMPEG, '-y', '-loglevel', 'error', '-f', 'gdigrab', '-framerate', '60', '-offset_x', str(x), '-offset_y', str(y),
            '-video_size', f'{ww}x{hh}'] + extra


def screenshot(path):
    """The game window (fullscreen: the whole display) to a PNG."""
    w = window()
    if not w: return False
    return subprocess.run(_grab(w, ['-i', 'desktop', '-frames:v', '1', path]), capture_output=True).returncode == 0


def record_start(path, secs):
    w = window()
    if not w: return None
    return subprocess.Popen(_grab(w, ['-i', 'desktop', '-t', str(secs), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16',
                                      '-pix_fmt', 'yuv420p', path]), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
