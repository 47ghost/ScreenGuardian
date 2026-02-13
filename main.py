


import sys
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class SettingsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ScreenGuardian 设置")
        self.resize(760, 460)
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        self.nav_list = QListWidget()
        self.nav_list.addItem("监控应用")
        self.nav_list.setFixedWidth(160)
        self.nav_list.setCurrentRow(0)

        self.stacked = QStackedWidget()
        self.stacked.addWidget(self._build_monitor_page())

        root_layout.addWidget(self.nav_list)
        root_layout.addWidget(self.stacked, 1)

        self.setCentralWidget(root)
        self.nav_list.currentRowChanged.connect(self.stacked.setCurrentIndex)

    def _build_monitor_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title = QLabel("监控应用")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")

        tip = QLabel("选择需要监控的应用程序可执行文件(.exe)。")
        tip.setStyleSheet("color: #666;")

        row = QHBoxLayout()
        self.exe_path_edit = QLineEdit()
        self.exe_path_edit.setPlaceholderText("请选择应用的 .exe 路径")
        self.exe_path_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        browse_button = QPushButton("选择程序")
        browse_button.setFixedWidth(100)
        browse_button.clicked.connect(self._choose_exe_path)

        row.addWidget(self.exe_path_edit, 1)
        row.addWidget(browse_button)

        layout.addWidget(title)
        layout.addWidget(tip)
        layout.addLayout(row)
        layout.addStretch(1)

        return page

    def _choose_exe_path(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择应用程序",
            "",
            "Executable (*.exe)",
        )
        if file_path:
            self.exe_path_edit.setText(file_path)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SettingsWindow()
    window.show()
    sys.exit(app.exec_())

