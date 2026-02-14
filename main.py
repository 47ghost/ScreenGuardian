


import json
import os
import sys
import time
import shutil
from datetime import datetime
from functools import partial
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QEvent, QObject
from PyQt5.QtGui import QPixmap, QCursor, QPainter, QBrush, QColor, QPen, QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QDialog,
    QMessageBox,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QVBoxLayout,
    QWidget,
    QGraphicsDropShadowEffect,
    QSystemTrayIcon,
    QMenu,
    QAction,
    QGroupBox,
    QFormLayout,
    QSlider,
    QSpinBox,
    QCheckBox,
)
from screen_capture import take_window_screenshot
from ai_chat import AIChatClient

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

class CaptureWorker(QThread):
    done_info = pyqtSignal(bool, str)
    def run(self):
        cfg_path = os.path.join(get_base_dir(), "data", "config", "monitor_apps.json")
        model_cfg_path = os.path.join(get_base_dir(), "data", "config", "model_config.json")
        apps = []
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                apps = (json.load(f) or {}).get("apps", [])
        except Exception:
            apps = []
        active = [a for a in apps if a.get("status") is True and a.get("name") and a.get("exe_path")]
        results = []
        for a in active:
            app_name = a.get("name", "").strip()
            exe_path = a.get("exe_path", "").strip()
            date_folder = datetime.now().strftime("%Y-%m-%d")
            timestamp = str(int(time.time()))
            base_dir = os.path.join(get_base_dir(), "data", "screenshot", app_name, date_folder)
            os.makedirs(base_dir, exist_ok=True)
            file_path = os.path.join(base_dir, f"{app_name}-{timestamp}.png")
            ok, saved_path = take_window_screenshot(exe_path, file_path)
            print((ok, saved_path))
            if ok and saved_path:
                results.append((a, saved_path))
        try:
            with open(model_cfg_path, "r", encoding="utf-8") as f:
                mcfg = json.load(f)
        except Exception:
            mcfg = {}
        api_key = mcfg.get("api_key", "")
        base_url = mcfg.get("base_url", "")
        beh = mcfg.get("behavior_analysis", {}) or {}
        model = beh.get("model", "")
        system_prompt = beh.get("system_prompt", "")
        behaviors = []
        if api_key and base_url and model:
            client = AIChatClient(api_key=api_key, base_url=base_url, model=model, system_prompt=system_prompt)
            for a, img in results:
                user_text = a.get("prompt", "") or ""
                try:
                    reply = client.chat(user_text=user_text, image_path=img)
                    print(reply)
                    behaviors.append(reply)
                except Exception as e:
                    print(str(e))
        if behaviors:
            log_dir = os.path.join(get_base_dir(), "data", "log")
            os.makedirs(log_dir, exist_ok=True)
            t = datetime.now().strftime("%Y-%m-%d %H:%M")
            entries = [{"time": t, "behavior": b} for b in behaviors]
            path = os.path.join(log_dir, "behavior-log.json")
            try:
                if os.path.isfile(path):
                    with open(path, "r", encoding="utf-8") as f:
                        old = json.load(f)
                    if isinstance(old, list):
                        entries = old + entries
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(entries, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        warn_no_entries = False
        reply_text = ""
        try:
            log_dir = os.path.join(get_base_dir(), "data", "log")
            bl_path = os.path.join(log_dir, "behavior-log.json")
            lines = []
            if os.path.isfile(bl_path):
                with open(bl_path, "r", encoding="utf-8") as f:
                    arr = json.load(f)
                if isinstance(arr, list) and arr:
                    tail = arr[-6:]
                    for item in tail:
                        t = str(item.get("time", ""))
                        b = str(item.get("behavior", ""))
                        lines.append(f"行为时间：{t} 行为：{b}")
            if not lines:
                warn_no_entries = False
                user_text = "要告知用户其应用截图功能未正常运行"
            else:
                user_text = "以下是用户最近的应用操作行为\n" + "\n".join(lines)
            api_key = mcfg.get("api_key", "")
            base_url = mcfg.get("base_url", "")
            syscfg = mcfg.get("system_call", {}) or {}
            sc_model = syscfg.get("model", "")
            sc_prompt = syscfg.get("system_prompt", "")
            if api_key and base_url and sc_model:
                sc_client = AIChatClient(api_key=api_key, base_url=base_url, model=sc_model, system_prompt=sc_prompt)
                reply_text = sc_client.chat(user_text=user_text, image_path=None)
                print(reply_text)
        except Exception as e:
            pass
        self.done_info.emit(warn_no_entries, reply_text)

class Signals(QObject):
    scale_changed = pyqtSignal(float)

global_signals = Signals()

class ChatWorker(QThread):
    reply_signal = pyqtSignal(str)

    def __init__(self, user_text):
        super().__init__()
        self.user_text = user_text

    def run(self):
        try:
            model_cfg_path = os.path.join(get_base_dir(), "data", "config", "model_config.json")
            with open(model_cfg_path, "r", encoding="utf-8") as f:
                mcfg = json.load(f)
            
            api_key = mcfg.get("api_key", "")
            base_url = mcfg.get("base_url", "")
            syscfg = mcfg.get("system_call", {}) or {}
            model = syscfg.get("model", "")
            system_prompt = syscfg.get("system_prompt", "")

            if api_key and base_url and model:
                client = AIChatClient(api_key=api_key, base_url=base_url, model=model, system_prompt=system_prompt)
                full_input = "用户现在不想提供应用活动日志，向你发送了对话聊天，内容如下" + self.user_text
                reply = client.chat(user_text=full_input, image_path=None)
                self.reply_signal.emit(reply)
            else:
                self.reply_signal.emit("配置缺失，请检查模型配置。")
        except Exception as e:
            self.reply_signal.emit(f"发生错误: {str(e)}")

class ChatDialog(QDialog):
    send_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(300, 150)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 8px;
            }
        """)
        container_layout = QVBoxLayout(self.container)
        
        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText("和我说说话吧...")
        self.input_edit.setStyleSheet("""
            QPlainTextEdit {
                border: none;
                background-color: transparent;
                font-size: 14px;
            }
        """)
        
        self.send_btn = QPushButton("发送")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
        """)
        self.send_btn.clicked.connect(self._on_send)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.send_btn)
        
        container_layout.addWidget(self.input_edit)
        container_layout.addLayout(btn_layout)
        
        layout.addWidget(self.container)
        
    def _on_send(self):
        text = self.input_edit.toPlainText().strip()
        if text:
            self.send_signal.emit(text)
            self.input_edit.clear()
            self.hide()
            
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self._on_send()
                event.accept()
        else:
            super().keyPressEvent(event)


class SpeechBubble(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.hide()
        
        # Increase padding for drawing background
        self.setContentsMargins(15, 15, 15, 15)
        
        # Style for text only
        self.setStyleSheet("""
            QLabel {
                color: #333333;
                font-family: "Microsoft YaHei";
                font-size: 14px;
                font-weight: bold;
            }
        """)
        self.setMaximumWidth(280)
        
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw background bubble
        rect = self.rect().adjusted(2, 2, -2, -2)
        
        # White background with high opacity
        brush = QBrush(QColor(255, 255, 255, 255))
        painter.setBrush(brush)
        
        # Light gray border
        pen = QPen(QColor(200, 200, 200))
        pen.setWidth(1)
        painter.setPen(pen)
        
        # Rounded rectangle
        painter.drawRoundedRect(rect, 10, 10)
        
        # Draw text
        super().paintEvent(event)

    def show_message(self, text, target_rect, screen_width, duration=10000):
        self.setText(text)
        self.adjustSize()
        
        # Calculate position
        bubble_width = self.width()
        bubble_height = self.height()
        
        pet_center_x = target_rect.center().x()
        
        # If character is on the left side of the screen (center < screen_width / 2)
        if pet_center_x < screen_width / 2:
            # Place bubble to the top-right of the character
            x = target_rect.right()
            y = target_rect.top()
        else:
            # Place bubble to the top-left of the character
            x = target_rect.left() - bubble_width
            y = target_rect.top()
            
        # Ensure y is not off-screen (simple check)
        if y < 0:
            y = 0
            
        self.move(x, y)
        self.show()
        self.timer.start(duration)

class ButtonPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.h_layout = QHBoxLayout(self)
        self.h_layout.setContentsMargins(0, 0, 0, 0)
        self.h_layout.setSpacing(10)
        self.hide()

class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ScreenGuardian 设置")
        self.resize(950, 600)
        
        icon_path = os.path.join(
            get_base_dir(),
            "data",
            "develop",
            "picture",
            "logo.ico",
        )
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        self.nav_list = QListWidget()
        self.nav_list.addItem("监控应用")
        self.nav_list.addItem("日志记录")
        self.nav_list.addItem("行为记录")
        self.nav_list.addItem("模型配置")
        self.nav_list.addItem("人物大小")
        self.nav_list.addItem("执行间隔")
        self.nav_list.setFixedWidth(180)
        self.nav_list.setStyleSheet("""
            QListWidget {
                background-color: #f5f5f5;
                border: none;
                outline: none;
            }
            QListWidget::item {
                height: 50px;
                padding-left: 15px;
                font-size: 14px;
                color: #555;
                border-left: 4px solid transparent;
            }
            QListWidget::item:selected {
                background-color: #ffffff;
                color: #333;
                font-weight: bold;
                border-left: 4px solid #4a90e2;
            }
            QListWidget::item:hover {
                background-color: #e0e0e0;
            }
        """)
        self.nav_list.setCurrentRow(0)

        self.stacked = QStackedWidget()
        self.stacked.addWidget(self._build_monitor_page())
        self.stacked.addWidget(self._build_logs_page())
        self.stacked.addWidget(self._build_behavior_page())
        self.stacked.addWidget(self._build_model_config_page())
        self.stacked.addWidget(self._build_scale_page())
        self.stacked.addWidget(self._build_interval_page())

        root_layout.addWidget(self.nav_list)
        root_layout.addWidget(self.stacked, 1)

        self.setCentralWidget(root)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)

    def _build_scale_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        title = QLabel("人物大小")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px;")
        
        description = QLabel("调整桌宠显示的缩放比例 (50% - 200%)")
        description.setStyleSheet("color: #666; font-size: 14px;")

        control_container = QWidget()
        control_container.setStyleSheet("""
            QWidget {
                background-color: #fff;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)
        h_layout = QHBoxLayout(control_container)
        h_layout.setContentsMargins(20, 30, 20, 30)
        h_layout.setSpacing(20)

        # Load current scale
        current_scale = 1.0
        config_path = os.path.join(get_base_dir(), "data", "config", "ui_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    ui_cfg = json.load(f)
                    current_scale = ui_cfg.get("scale", 1.0)
            except:
                pass

        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(50, 200)
        self.scale_slider.setValue(int(current_scale * 100))
        self.scale_slider.setTickPosition(QSlider.TicksBelow)
        self.scale_slider.setTickInterval(10)
        self.scale_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #ccc;
                height: 8px;
                background: #f0f0f0;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #4a90e2;
                border: 1px solid #4a90e2;
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
        """)

        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(50, 200)
        self.scale_spin.setValue(int(current_scale * 100))
        self.scale_spin.setSuffix("%")
        self.scale_spin.setFixedWidth(80)
        self.scale_spin.setStyleSheet("""
            QSpinBox {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
                font-size: 14px;
            }
        """)

        self.scale_slider.valueChanged.connect(self.scale_spin.setValue)
        self.scale_spin.valueChanged.connect(self.scale_slider.setValue)
        self.scale_slider.valueChanged.connect(self._on_scale_changed)

        h_layout.addWidget(QLabel("缩放:"))
        h_layout.addWidget(self.scale_slider)
        h_layout.addWidget(self.scale_spin)

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(control_container)
        layout.addStretch(1)

        return page

    def _build_interval_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        title = QLabel("执行间隔")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px;")
        
        description = QLabel("配置自动执行捕获屏幕的时间间隔。")
        description.setStyleSheet("color: #666; font-size: 14px;")

        control_container = QWidget()
        control_container.setStyleSheet("""
            QWidget {
                background-color: #fff;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)
        form_layout = QFormLayout(control_container)
        form_layout.setContentsMargins(20, 30, 20, 30)
        form_layout.setSpacing(20)

        # Load current config
        self.interval_enabled = False
        self.interval_minutes = 10
        config_path = os.path.join(get_base_dir(), "data", "config", "interval_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.interval_enabled = cfg.get("enabled", False)
                    self.interval_minutes = cfg.get("interval", 10)
            except:
                pass

        self.interval_check = QCheckBox("开启自动执行")
        self.interval_check.setChecked(self.interval_enabled)
        self.interval_check.setStyleSheet("font-size: 14px;")
        
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 1440) # 1 min to 24 hours
        self.interval_spin.setValue(self.interval_minutes)
        self.interval_spin.setSuffix(" 分钟")
        self.interval_spin.setFixedWidth(120)
        self.interval_spin.setStyleSheet("""
            QSpinBox {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
                font-size: 14px;
            }
        """)

        self.interval_check.stateChanged.connect(self._save_interval_config)
        self.interval_spin.valueChanged.connect(self._save_interval_config)

        form_layout.addRow("状态:", self.interval_check)
        form_layout.addRow("间隔:", self.interval_spin)

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(control_container)
        layout.addStretch(1)

        return page

    def _save_interval_config(self):
        enabled = self.interval_check.isChecked()
        interval = self.interval_spin.value()
        
        config_path = os.path.join(get_base_dir(), "data", "config", "interval_config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"enabled": enabled, "interval": interval}, f)
        except:
            pass

    def _on_scale_changed(self, value):
        scale = value / 100.0
        # Save to config
        config_path = os.path.join(get_base_dir(), "data", "config", "ui_config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"scale": scale}, f)
        except:
            pass
        
        # Emit signal to update main window
        global_signals.scale_changed.emit(scale)

    def _build_monitor_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        title = QLabel("监控应用")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")

        tip = QLabel("配置需要监控的应用程序。当应用运行时，将会自动捕获并分析用户行为。")
        tip.setStyleSheet("color: #666; font-size: 13px; margin-bottom: 10px;")
        tip.setWordWrap(True)

        self.app_rows_container = QWidget()
        self.app_rows_container.setStyleSheet("background-color: transparent;")
        self.app_rows_layout = QVBoxLayout(self.app_rows_container)
        self.app_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.app_rows_layout.setSpacing(15)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.app_rows_container)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                border: none;
                background: #f0f0f0;
                width: 8px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #ccc;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        self._config_path = os.path.join(get_base_dir(), "data", "config", "monitor_apps.json")
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        data = self._load_monitor_config()
        self.app_slots = []
        for idx in range(1, 5):
            slot_data = next((x for x in data if x.get("id") == idx), None)
            row = self._build_app_slot(idx, slot_data or {"id": idx, "status": False, "name": "", "exe_path": "", "prompt": ""})
            self.app_rows_layout.addWidget(row)

        layout.addWidget(title)
        layout.addWidget(tip)
        layout.addWidget(scroll)
        
        return page
    
    def _on_nav_changed(self, idx):
        self.stacked.setCurrentIndex(idx)
        if idx == 1 and hasattr(self, "_logs_table"):
            self._populate_logs_table(self._logs_table)
        if idx == 2 and hasattr(self, "_behavior_table"):
            self._populate_behavior_table(self._behavior_table)

    def _build_model_config_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        title = QLabel("模型配置")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px;")
        layout.addWidget(title)

        self._model_config_path = os.path.join(get_base_dir(), "data", "config", "model_config.json")
        os.makedirs(os.path.dirname(self._model_config_path), exist_ok=True)
        cfg = self._load_model_config()

        # Global Config Group
        g1 = QGroupBox("基础设置")
        g1.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #555;
            }
        """)
        g1_layout = QFormLayout(g1)
        g1_layout.setContentsMargins(15, 20, 15, 15)
        g1_layout.setSpacing(15)
        
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setText(cfg.get("api_key", ""))
        self.api_key_edit.setPlaceholderText("sk-...")
        # self.api_key_edit.setEchoMode(QLineEdit.Password)
        
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setText(cfg.get("base_url", ""))
        self.base_url_edit.setPlaceholderText("https://api.example.com/v1")
        
        g1_layout.addRow("API Key:", self.api_key_edit)
        g1_layout.addRow("Base URL:", self.base_url_edit)
        
        layout.addWidget(g1)

        syscall = cfg.get("system_call", {})
        behavior = cfg.get("behavior_analysis", {})

        # System Call Group
        g2 = QGroupBox("系统调用")
        g2.setStyleSheet(g1.styleSheet())
        g2_layout = QFormLayout(g2)
        g2_layout.setContentsMargins(15, 20, 15, 15)
        g2_layout.setSpacing(15)
        
        self.syscall_model_edit = QLineEdit()
        self.syscall_model_edit.setText(syscall.get("model", ""))
        self.syscall_model_edit.setPlaceholderText("gpt-3.5-turbo")
        
        self.syscall_prompt_edit = QPlainTextEdit()
        self.syscall_prompt_edit.setPlainText(syscall.get("system_prompt", ""))
        self.syscall_prompt_edit.setPlaceholderText("输入系统调用提示词...")
        self.syscall_prompt_edit.setFixedHeight(60)
        
        g2_layout.addRow("模型名称:", self.syscall_model_edit)
        g2_layout.addRow("提示词:", self.syscall_prompt_edit)
        
        layout.addWidget(g2)

        # Behavior Analysis Group
        g3 = QGroupBox("行为分析")
        g3.setStyleSheet(g1.styleSheet())
        g3_layout = QFormLayout(g3)
        g3_layout.setContentsMargins(15, 20, 15, 15)
        g3_layout.setSpacing(15)
        
        self.behavior_model_edit = QLineEdit()
        self.behavior_model_edit.setText(behavior.get("model", ""))
        self.behavior_model_edit.setPlaceholderText("gpt-4-vision-preview")
        
        self.behavior_prompt_edit = QPlainTextEdit()
        self.behavior_prompt_edit.setPlainText(behavior.get("system_prompt", ""))
        self.behavior_prompt_edit.setPlaceholderText("输入行为分析提示词...")
        self.behavior_prompt_edit.setFixedHeight(60)
        
        g3_layout.addRow("模型名称:", self.behavior_model_edit)
        g3_layout.addRow("提示词:", self.behavior_prompt_edit)
        
        layout.addWidget(g3)
        
        # Style all inputs
        input_style = """
            QLineEdit, QPlainTextEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 6px;
                background-color: #fff;
            }
            QLineEdit:focus, QPlainTextEdit:focus {
                border: 1px solid #4a90e2;
            }
        """
        page.setStyleSheet(input_style)

        save_row = QHBoxLayout()
        save_button = QPushButton("保存配置")
        save_button.setCursor(Qt.PointingHandCursor)
        save_button.setFixedSize(120, 36)
        save_button.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:pressed {
                background-color: #2a5d8f;
            }
        """)
        save_button.clicked.connect(self._save_model_config)
        save_row.addStretch(1)
        save_row.addWidget(save_button)

        layout.addLayout(save_row)
        layout.addStretch(1)
        return page

    def _load_model_config(self):
        if os.path.isfile(self._model_config_path):
            try:
                with open(self._model_config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "api_key": "",
            "base_url": "",
            "system_call": {"model": "", "system_prompt": ""},
            "behavior_analysis": {"model": "", "system_prompt": ""},
        }

    def _save_model_config(self):
        data = {
            "api_key": self.api_key_edit.text().strip(),
            "base_url": self.base_url_edit.text().strip(),
            "system_call": {
                "model": self.syscall_model_edit.text().strip(),
                "system_prompt": self.syscall_prompt_edit.toPlainText().strip(),
            },
            "behavior_analysis": {
                "model": self.behavior_model_edit.text().strip(),
                "system_prompt": self.behavior_prompt_edit.toPlainText().strip(),
            },
        }
        try:
            with open(self._model_config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "提示", "保存成功")
        except Exception as e:
            QMessageBox.warning(self, "错误", "保存失败")

    def _build_logs_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title = QLabel("日志记录")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")

        table = QTableWidget()
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["时间", "模型", "用户输入", "模型回答"])
        table.setWordWrap(True)
        self._populate_logs_table(table)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.cellDoubleClicked.connect(self._on_log_cell_double_clicked)

        layout.addWidget(title)
        layout.addWidget(table, 1)
        actions = QHBoxLayout()
        clear_button = QPushButton("清除日志")
        clear_button.clicked.connect(self._clear_logs_and_refresh)
        actions.addStretch(1)
        actions.addWidget(clear_button)
        layout.addLayout(actions)
        return page

    def _populate_logs_table(self, table: QTableWidget):
        log_dir = os.path.join(get_base_dir(), "data", "log")
        entries = []
        path = os.path.join(log_dir, "logs.jsonl")
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            entries.append(obj)
                        except Exception:
                            pass
            except Exception:
                pass
        table.setRowCount(len(entries))
        for i, e in enumerate(entries):
            time_item = QTableWidgetItem(str(e.get("time", "")))
            model_item = QTableWidgetItem(str(e.get("model", "")))
            user_input = "用户输入内容:" + str(e.get("user_input_content", "")) + "\n" + "系统提示词:" + str(e.get("system_prompt", "")) + "\n" + "图片内容:" + str(e.get("image", "无上传图片"))
            user_item = QTableWidgetItem(user_input)
            reply_item = QTableWidgetItem(str(e.get("reply", "")))
            table.setItem(i, 0, time_item)
            table.setItem(i, 1, model_item)
            table.setItem(i, 2, user_item)
            table.setItem(i, 3, reply_item)
        self._logs_table = table

    def _build_behavior_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title = QLabel("行为记录")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")

        table = QTableWidget()
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["时间", "行为"])
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.cellDoubleClicked.connect(self._on_behavior_cell_double_clicked)
        self._populate_behavior_table(table)

        actions = QHBoxLayout()
        clear_button = QPushButton("清除行为日志")
        clear_button.clicked.connect(self._clear_behavior_logs_and_refresh)
        actions.addStretch(1)
        actions.addWidget(clear_button)

        layout.addWidget(title)
        layout.addWidget(table, 1)
        layout.addLayout(actions)
        self._behavior_table = table
        return page

    def _populate_behavior_table(self, table: QTableWidget):
        log_dir = os.path.join(get_base_dir(), "data", "log")
        path = os.path.join(log_dir, "behavior-log.json")
        entries = []
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    entries = json.load(f)
                if not isinstance(entries, list):
                    entries = []
            except Exception:
                entries = []
        table.setRowCount(len(entries))
        for i, e in enumerate(entries):
            time_item = QTableWidgetItem(str(e.get("time", "")))
            behavior_item = QTableWidgetItem(str(e.get("behavior", "")))
            table.setItem(i, 0, time_item)
            table.setItem(i, 1, behavior_item)
        self._behavior_table = table

    def _clear_behavior_logs_and_refresh(self):
        log_dir = os.path.join(get_base_dir(), "data", "log")
        path = os.path.join(log_dir, "behavior-log.json")
        if os.path.isfile(path):
            try:
                os.remove(path)
            except Exception:
                pass
        # Also clear all screenshots under data/screenshot
        shots_dir = os.path.join(get_base_dir(), "data", "screenshot")
        if os.path.isdir(shots_dir):
            try:
                shutil.rmtree(shots_dir, ignore_errors=True)
                os.makedirs(shots_dir, exist_ok=True)
            except Exception:
                pass
        if hasattr(self, "_behavior_table"):
            self._populate_behavior_table(self._behavior_table)

    def _on_behavior_cell_double_clicked(self, row, col):
        if not hasattr(self, "_behavior_table"):
            return
        item = self._behavior_table.item(row, col)
        if not item:
            return
        title = "行为详情"
        self._show_text_dialog(title, item.text())

    def _clear_logs_and_refresh(self):
        log_dir = os.path.join(get_base_dir(), "data", "log")
        path = os.path.join(log_dir, "logs.jsonl")
        if os.path.isfile(path):
            try:
                os.remove(path)
            except Exception:
                pass
        if hasattr(self, "_logs_table"):
            self._populate_logs_table(self._logs_table)

    def _on_log_cell_double_clicked(self, row, col):
        if col not in (2, 3):
            return
        if not hasattr(self, "_logs_table"):
            return
        item = self._logs_table.item(row, col)
        if not item:
            return
        title = "用户输入详情" if col == 2 else "模型回答详情"
        self._show_text_dialog(title, item.text())

    def _show_text_dialog(self, title, text):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.setSizeGripEnabled(True)
        v = QVBoxLayout(dlg)
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(text)
        v.addWidget(editor)
        actions = QHBoxLayout()
        actions.addStretch(1)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dlg.accept)
        actions.addWidget(close_btn)
        v.addLayout(actions)
        dlg.resize(700, 480)
        dlg.exec_()

    def _build_app_slot(self, slot_id, slot_data):
        container = QGroupBox(f"应用槽位 {slot_id}")
        container.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 6px;
                margin-top: 10px;
                background-color: #fff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #4a90e2;
            }
        """)
        v = QVBoxLayout(container)
        v.setContentsMargins(15, 20, 15, 15)
        v.setSpacing(10)

        # Row 1: Name and Path
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText("应用名称 (例如: 微信)")
        name_edit.setFixedWidth(180)
        name_edit.setText(slot_data.get("name", ""))
        
        path_edit = QLineEdit()
        path_edit.setPlaceholderText("请选择应用程序路径 (.exe)")
        path_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        path_edit.setText(slot_data.get("exe_path", ""))
        
        browse_button = QPushButton("浏览...")
        browse_button.setCursor(Qt.PointingHandCursor)
        browse_button.setFixedWidth(80)
        browse_button.clicked.connect(partial(self._choose_exe_path, path_edit))
        
        row1.addWidget(QLabel("名称:"))
        row1.addWidget(name_edit)
        row1.addWidget(QLabel("路径:"))
        row1.addWidget(path_edit, 1)
        row1.addWidget(browse_button)

        # Row 2: Prompt
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        
        prompt_label = QLabel("提示词:")
        prompt_edit = QLineEdit()
        prompt_edit.setPlaceholderText("请输入行为分析提示词...")
        default_prompt = self._default_prompt(name_edit.text())
        prompt_text = slot_data.get("prompt", "")
        prompt_edit.setText(prompt_text or default_prompt)
        
        test_button = QPushButton("测试")
        test_button.setCursor(Qt.PointingHandCursor)
        test_button.setFixedWidth(80)
        test_button.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white; 
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        test_button.clicked.connect(partial(self._test_capture, name_edit, path_edit))

        row2.addWidget(prompt_label)
        row2.addWidget(prompt_edit, 1)
        row2.addWidget(test_button)
        
        v.addLayout(row1)
        v.addLayout(row2)

        # Apply styles to inputs/buttons in this group
        container.setStyleSheet(container.styleSheet() + """
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
            }
            QLineEdit:focus {
                border: 1px solid #4a90e2;
            }
            QPushButton {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
                background-color: #f8f9fa;
                color: #333;
            }
            QPushButton:hover {
                background-color: #e2e6ea;
            }
        """)

        self.app_slots.append({
            "id": slot_id,
            "name_edit": name_edit,
            "path_edit": path_edit,
            "prompt_edit": prompt_edit,
        })
        name_edit.textChanged.connect(partial(self._on_name_changed, slot_id))
        name_edit.textChanged.connect(self._save_monitor_config)
        path_edit.textChanged.connect(self._save_monitor_config)
        prompt_edit.textChanged.connect(self._save_monitor_config)

        return container

    def _choose_exe_path(self, target_edit):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择应用程序",
            "",
            "Executable (*.exe)",
        )
        if file_path:
            target_edit.setText(file_path)

    def _sanitize_name(self, raw_name):
        if not raw_name:
            return "未命名应用"
        invalid = '<>:"/\\|?*'
        cleaned = "".join("_" if c in invalid else c for c in raw_name)
        return cleaned.strip() or "未命名应用"

    def _default_prompt(self, app_name):
        if not app_name:
            return "这是应用，需要分析图片中用户在进行什么操作"
        return f"这是“{app_name}”应用，需要分析图片中用户在进行什么操作"

    def _on_name_changed(self, slot_id):
        slot = next((s for s in self.app_slots if s["id"] == slot_id), None)
        if not slot:
            return
        name_text = slot["name_edit"].text().strip()
        current_prompt = slot["prompt_edit"].text().strip()
        if not current_prompt or current_prompt.startswith("这是"):
            slot["prompt_edit"].setText(self._default_prompt(name_text))

    def _test_capture(self, name_edit, path_edit):
        exe_path = path_edit.text().strip()
        if not exe_path:
            return
        app_name = self._sanitize_name(name_edit.text())
        date_folder = datetime.now().strftime("%Y-%m-%d")
        timestamp = str(int(time.time()))
        base_dir = os.path.join(get_base_dir(), "data", "screenshot", app_name, date_folder)
        os.makedirs(base_dir, exist_ok=True)
        file_path = os.path.join(base_dir, f"{app_name}-{timestamp}.png")
        ok, saved_path = take_window_screenshot(exe_path, file_path)
        print((ok, saved_path))

    def _load_monitor_config(self):
        if not os.path.isfile(self._config_path):
            return [{"id": i, "status": False, "name": "", "exe_path": "", "prompt": ""} for i in range(1, 5)]
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            apps = obj.get("apps")
            if isinstance(apps, list):
                return apps
        except Exception:
            pass
        return [{"id": i, "status": False, "name": "", "exe_path": "", "prompt": ""} for i in range(1, 5)]

    def _save_monitor_config(self):
        apps = []
        for slot in self.app_slots:
            name = slot["name_edit"].text().strip()
            path = slot["path_edit"].text().strip()
            prompt = slot["prompt_edit"].text().strip()
            status = bool(name and path)
            apps.append({
                "id": slot["id"],
                "status": status,
                "name": name,
                "exe_path": path,
                "prompt": prompt,
            })
        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump({"apps": apps}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

class PetWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.settings_window = None
        self.drag_offset = None
        self.capture_worker = None
        self.capture_running = False
        
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.setInterval(300) # 0.3s
        self.hover_timer.timeout.connect(self._show_buttons)

        self.hide_buttons_timer = QTimer(self)
        self.hide_buttons_timer.setSingleShot(True)
        self.hide_buttons_timer.setInterval(3000) # 3s
        self.hide_buttons_timer.timeout.connect(self._hide_buttons)
        
        self._build_ui()
        self._init_tray_icon()

    def _on_loop_tick(self):
        enabled = False
        interval_min = 10
        
        config_path = os.path.join(get_base_dir(), "data", "config", "interval_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    enabled = cfg.get("enabled", False)
                    interval_min = cfg.get("interval", 10)
            except:
                pass
        
        if enabled:
            self._capture_all()
            next_delay = interval_min * 60 * 1000
        else:
            # Check again in 1 minute
            next_delay = 60 * 1000
            
        self.loop_timer.start(next_delay)

    def _init_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        image_path = os.path.join(
            get_base_dir(),
            "data",
            "develop",
            "picture",
            "logo.ico",
        )
        if os.path.exists(image_path):
            self.tray_icon.setIcon(QIcon(image_path))
        
        self.tray_icon.setToolTip("ScreenGuardian")
        
        tray_menu = QMenu()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def _build_ui(self):
        self.setWindowTitle("ScreenGuardian")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        icon_path = os.path.join(
            get_base_dir(),
            "data",
            "develop",
            "picture",
            "logo.ico",
        )
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Init interval timer
        self.loop_timer = QTimer(self)
        self.loop_timer.setSingleShot(True)
        self.loop_timer.timeout.connect(self._on_loop_tick)
        # First check in 1 minute (60000ms)
        self.loop_timer.start(60000)

        # Speech Bubble
        self.speech_bubble = SpeechBubble()
        
        # Chat Dialog
        self.chat_dialog = ChatDialog(self)
        self.chat_dialog.send_signal.connect(self._on_chat_send)
        
        # Image Label
        self.image_label = QLabel()
        image_path = os.path.join(
            get_base_dir(),
            "data",
            "develop",
            "picture",
            "main.png",
        )
        self.original_pixmap = QPixmap(image_path)
        
        # Load scale config
        self.current_scale = 1.0
        config_path = os.path.join(get_base_dir(), "data", "config", "ui_config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    ui_cfg = json.load(f)
                    self.current_scale = ui_cfg.get("scale", 1.0)
            except:
                pass

        self._update_image_scale()
        
        self.image_label.installEventFilter(self)
        layout.addWidget(self.image_label, alignment=Qt.AlignCenter)

        # Button Panel
        self.button_panel = ButtonPanel()
        self.button_panel.installEventFilter(self)
        
        chat_button = QPushButton("对话")
        chat_button.clicked.connect(self._open_chat)
        self.capture_button = QPushButton("捕获屏幕")
        settings_button = QPushButton("设置")
        exit_button = QPushButton("退出")
        
        settings_button.clicked.connect(self._open_settings)
        self.capture_button.clicked.connect(self._capture_all)
        exit_button.clicked.connect(QApplication.instance().quit)
        
        for btn in [chat_button, self.capture_button, settings_button, exit_button]:
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #4a90e2;
                    color: white;
                    border-radius: 5px;
                    padding: 5px 10px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #357abd;
                }
                QPushButton:pressed {
                    background-color: #2a5d8f;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                }
            """)
            self.button_panel.h_layout.addWidget(btn)

        layout.addWidget(self.button_panel)
        layout.addStretch(1)
        
        self.adjustSize()
        
        # Connect signal
        global_signals.scale_changed.connect(self._on_scale_changed)

    def _update_image_scale(self):
        if self.original_pixmap.isNull():
            self.image_label.setText("主形象图片未找到")
        else:
            base_scale = 0.35 # Original base scale
            final_scale = base_scale * self.current_scale
            scaled = self.original_pixmap.scaled(
                int(self.original_pixmap.width() * final_scale),
                int(self.original_pixmap.height() * final_scale),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
            self.image_label.setFixedSize(scaled.size())
            self.adjustSize()

    def _on_scale_changed(self, scale):
        self.current_scale = scale
        self._update_image_scale()

    def eventFilter(self, obj, event):
        if obj == self.image_label:
            if event.type() == QEvent.Enter:
                self.hover_timer.start()
            elif event.type() == QEvent.Leave:
                self.hover_timer.stop()
                if self.button_panel.isVisible():
                    self.hide_buttons_timer.start()
        elif obj == self.button_panel:
            if event.type() == QEvent.Enter:
                self.hide_buttons_timer.stop()
            elif event.type() == QEvent.Leave:
                self.hide_buttons_timer.start()
        return super().eventFilter(obj, event)

    def _show_buttons(self):
        self.button_panel.show()
        self.hide_buttons_timer.start()
        self.adjustSize()

    def _hide_buttons(self):
        self.button_panel.hide()
        self.adjustSize()

    def _open_settings(self):
        if self.settings_window is None:
            self.settings_window = SettingsWindow()
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def _capture_all(self):
        if self.capture_running:
            return
        self.capture_running = True
        self.capture_button.setEnabled(False)
        self.capture_worker = CaptureWorker(self)
        self.capture_worker.done_info.connect(self._on_capture_done_info)
        self.capture_worker.finished.connect(self._on_capture_finished)
        self.capture_worker.start()

    def _on_capture_finished(self):
        self.capture_running = False
        self.capture_button.setEnabled(True)
    
    def _on_capture_done_info(self, warn, reply_text):
        if reply_text:
            screen = QApplication.primaryScreen()
            screen_geom = screen.availableGeometry()
            self.speech_bubble.show_message(reply_text, self.geometry(), screen_geom.width())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self.drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_offset = None
            event.accept()

    def _open_chat(self):
        # Calculate position based on window geometry
        window_rect = self.geometry()
        # Center horizontally relative to window
        x = window_rect.x() + (window_rect.width() - self.chat_dialog.width()) // 2
        # Place below the window
        y = window_rect.y() + window_rect.height() + 10
        
        # Ensure it's on screen
        screen = QApplication.primaryScreen()
        screen_geom = screen.availableGeometry()
        
        if y + self.chat_dialog.height() > screen_geom.bottom():
            # If too low, place above
            y = window_rect.y() - self.chat_dialog.height() - 10
            
        self.chat_dialog.move(x, y)
        self.chat_dialog.show()
        self.chat_dialog.activateWindow()
        self.chat_dialog.input_edit.setFocus()

    def _on_chat_send(self, text):
        screen = QApplication.primaryScreen()
        screen_geom = screen.availableGeometry()
        self.speech_bubble.show_message("正在思考...", self.geometry(), screen_geom.width())
        
        # Keep a reference to prevent garbage collection
        self.chat_worker = ChatWorker(text)
        self.chat_worker.reply_signal.connect(self._on_chat_reply)
        self.chat_worker.start()
        
    def _on_chat_reply(self, reply):
        screen = QApplication.primaryScreen()
        screen_geom = screen.availableGeometry()
        self.speech_bubble.show_message(reply, self.geometry(), screen_geom.width())



if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = PetWindow()
    window.show()
    sys.exit(app.exec_())

