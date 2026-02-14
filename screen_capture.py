import ctypes
import os
from ctypes import wintypes
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication


def take_window_screenshot(exe_path, file_path):
    hwnd = find_window_by_exe_path(exe_path)
    if hwnd is None:
        return (False, None)
    user32 = ctypes.windll.user32
    if user32.IsIconic(hwnd):
        return (False, None)
    if capture_window_to_file(hwnd, file_path):
        return (True, file_path)
    screen = QApplication.primaryScreen()
    if screen is None:
        return (False, None)
    pixmap = screen.grabWindow(int(hwnd))
    ok = pixmap.save(file_path, "PNG")
    return (bool(ok), file_path if ok else None)


def find_window_by_exe_path(exe_path):
    target = os.path.normcase(os.path.normpath(exe_path))
    if not target:
        return None
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    hwnds = []
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0:
            return True
        h_process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not h_process:
            return True
        try:
            buf_len = wintypes.DWORD(32767)
            exe_buf = ctypes.create_unicode_buffer(buf_len.value)
            if kernel32.QueryFullProcessImageNameW(h_process, 0, exe_buf, ctypes.byref(buf_len)):
                candidate = os.path.normcase(os.path.normpath(exe_buf.value))
                if candidate == target:
                    hwnds.append(hwnd)
                    return False
        finally:
            kernel32.CloseHandle(h_process)
        return True

    user32.EnumWindows(enum_proc, 0)
    return hwnds[0] if hwnds else None


def capture_window_to_file(hwnd, file_path):
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        return False
    hwindc = user32.GetWindowDC(hwnd)
    if not hwindc:
        return False
    memdc = gdi32.CreateCompatibleDC(hwindc)
    if not memdc:
        user32.ReleaseDC(hwnd, hwindc)
        return False
    bitmap = gdi32.CreateCompatibleBitmap(hwindc, width, height)
    if not bitmap:
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(hwnd, hwindc)
        return False
    gdi32.SelectObject(memdc, bitmap)
    PW_RENDERFULLCONTENT = 0x00000002
    printed = user32.PrintWindow(hwnd, memdc, PW_RENDERFULLCONTENT)
    if not printed:
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(hwnd, hwindc)
        return False

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
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0
    buffer_size = width * height * 4
    buffer = ctypes.create_string_buffer(buffer_size)
    bits = gdi32.GetDIBits(memdc, bitmap, 0, height, buffer, ctypes.byref(bmi), 0)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memdc)
    user32.ReleaseDC(hwnd, hwindc)
    if bits == 0:
        return False
    image = QImage(buffer, width, height, width * 4, QImage.Format_ARGB32)
    return image.save(file_path)
