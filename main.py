


import json
import os
import sys
import time
from datetime import datetime
from functools import partial
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap
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
)
from screen_capture import take_window_screenshot
from ai_chat import AIChatClient

class CaptureWorker(QThread):
    done_info = pyqtSignal(bool, str)
    def run(self):
        cfg_path = os.path.join(os.getcwd(), "data", "config", "monitor_apps.json")
        model_cfg_path = os.path.join(os.getcwd(), "data", "config", "model_config.json")
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
            base_dir = os.path.join(os.getcwd(), "data", "screenshot", app_name, date_folder)
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
            log_dir = os.path.join(os.getcwd(), "data", "log")
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
            log_dir = os.path.join(os.getcwd(), "data", "log")
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

class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ScreenGuardian 设置")
        self.resize(950, 600)
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
        self.nav_list.setFixedWidth(160)
        self.nav_list.setCurrentRow(0)

        self.stacked = QStackedWidget()
        self.stacked.addWidget(self._build_monitor_page())
        self.stacked.addWidget(self._build_logs_page())
        self.stacked.addWidget(self._build_behavior_page())
        self.stacked.addWidget(self._build_model_config_page())

        root_layout.addWidget(self.nav_list)
        root_layout.addWidget(self.stacked, 1)

        self.setCentralWidget(root)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)

    def _build_monitor_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title = QLabel("监控应用")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")

        tip = QLabel("固定 4 个应用槽位，填写应用名、路径与提示词，点击测试。")
        tip.setStyleSheet("color: #666;")

        self.app_rows_container = QWidget()
        self.app_rows_layout = QVBoxLayout(self.app_rows_container)
        self.app_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.app_rows_layout.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.app_rows_container)

        self._config_path = os.path.join(os.getcwd(), "data", "config", "monitor_apps.json")
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
        layout.addStretch(1)

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
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title = QLabel("模型配置")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")

        self._model_config_path = os.path.join(os.getcwd(), "data", "config", "model_config.json")
        os.makedirs(os.path.dirname(self._model_config_path), exist_ok=True)
        cfg = self._load_model_config()

        g1 = QHBoxLayout()
        l_api = QLabel("API Key")
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setText(cfg.get("api_key", ""))
        l_base = QLabel("Base URL")
        self.base_url_edit = QLineEdit()
        self.base_url_edit.setText(cfg.get("base_url", ""))
        g1.addWidget(l_api)
        g1.addWidget(self.api_key_edit, 1)
        g1.addWidget(l_base)
        g1.addWidget(self.base_url_edit, 1)

        syscall = cfg.get("system_call", {})
        behavior = cfg.get("behavior_analysis", {})

        g2 = QHBoxLayout()
        l_sys_model = QLabel("系统调用 Model")
        self.syscall_model_edit = QLineEdit()
        self.syscall_model_edit.setText(syscall.get("model", ""))
        l_sys_prompt = QLabel("系统调用 提示词")
        self.syscall_prompt_edit = QLineEdit()
        self.syscall_prompt_edit.setText(syscall.get("system_prompt", ""))
        g2.addWidget(l_sys_model)
        g2.addWidget(self.syscall_model_edit, 1)
        g2.addWidget(l_sys_prompt)
        g2.addWidget(self.syscall_prompt_edit, 1)

        g3 = QHBoxLayout()
        l_beh_model = QLabel("行为分析 Model")
        self.behavior_model_edit = QLineEdit()
        self.behavior_model_edit.setText(behavior.get("model", ""))
        l_beh_prompt = QLabel("行为分析 提示词")
        self.behavior_prompt_edit = QLineEdit()
        self.behavior_prompt_edit.setText(behavior.get("system_prompt", ""))
        g3.addWidget(l_beh_model)
        g3.addWidget(self.behavior_model_edit, 1)
        g3.addWidget(l_beh_prompt)
        g3.addWidget(self.behavior_prompt_edit, 1)

        save_row = QHBoxLayout()
        save_button = QPushButton("保存")
        save_button.clicked.connect(self._save_model_config)
        save_row.addStretch(1)
        save_row.addWidget(save_button)

        layout.addWidget(title)
        layout.addLayout(g1)
        layout.addLayout(g2)
        layout.addLayout(g3)
        layout.addLayout(save_row)
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
                "system_prompt": self.syscall_prompt_edit.text().strip(),
            },
            "behavior_analysis": {
                "model": self.behavior_model_edit.text().strip(),
                "system_prompt": self.behavior_prompt_edit.text().strip(),
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
        log_dir = os.path.join(os.getcwd(), "data", "log")
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
        log_dir = os.path.join(os.getcwd(), "data", "log")
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
        log_dir = os.path.join(os.getcwd(), "data", "log")
        path = os.path.join(log_dir, "behavior-log.json")
        if os.path.isfile(path):
            try:
                os.remove(path)
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
        log_dir = os.path.join(os.getcwd(), "data", "log")
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
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText("应用名称")
        name_edit.setFixedWidth(160)
        name_edit.setText(slot_data.get("name", ""))

        path_edit = QLineEdit()
        path_edit.setPlaceholderText("请选择应用的 .exe 路径")
        path_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        path_edit.setText(slot_data.get("exe_path", ""))

        browse_button = QPushButton("选择程序")
        browse_button.setFixedWidth(90)
        browse_button.clicked.connect(partial(self._choose_exe_path, path_edit))

        test_button = QPushButton("测试")
        test_button.setFixedWidth(70)
        test_button.clicked.connect(partial(self._test_capture, name_edit, path_edit))

        row_layout.addWidget(QLabel(f"槽位 {slot_id}"))
        row_layout.addWidget(name_edit)
        row_layout.addWidget(path_edit, 1)
        row_layout.addWidget(browse_button)
        row_layout.addWidget(test_button)

        prompt_layout = QHBoxLayout()
        prompt_label = QLabel("提示词")
        prompt_edit = QLineEdit()
        prompt_edit.setPlaceholderText("请输入提示词")
        default_prompt = self._default_prompt(name_edit.text())
        prompt_text = slot_data.get("prompt", "")
        prompt_edit.setText(prompt_text or default_prompt)
        prompt_layout.addWidget(prompt_label)
        prompt_layout.addWidget(prompt_edit, 1)

        v.addLayout(row_layout)
        v.addLayout(prompt_layout)

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
        base_dir = os.path.join(os.getcwd(), "data", "screenshot", app_name, date_folder)
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
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("ScreenGuardian")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        image_label = QLabel()
        image_path = os.path.join(
            os.path.dirname(__file__),
            "data",
            "develop",
            "picture",
            "main.png",
        )
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            image_label.setText("主形象图片未找到")
        else:
            scaled = pixmap.scaled(
                int(pixmap.width() * 0.35),
                int(pixmap.height() * 0.35),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            image_label.setPixmap(scaled)
            image_label.setFixedSize(scaled.size())

        button_row = QHBoxLayout()
        chat_button = QPushButton("对话")
        self.capture_button = QPushButton("捕获屏幕")
        settings_button = QPushButton("设置")
        exit_button = QPushButton("退出")
        settings_button.clicked.connect(self._open_settings)
        self.capture_button.clicked.connect(self._capture_all)
        exit_button.clicked.connect(QApplication.instance().quit)
        button_row.addWidget(chat_button)
        button_row.addWidget(self.capture_button)
        button_row.addWidget(settings_button)
        button_row.addWidget(exit_button)

        layout.addWidget(image_label, alignment=Qt.AlignCenter)
        layout.addLayout(button_row)
        layout.addStretch(1)
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
        return

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PetWindow()
    window.show()
    sys.exit(app.exec_())

