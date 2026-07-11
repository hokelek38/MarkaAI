from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel

from ui.theme import Theme


class Sidebar(QWidget):

    page_changed = Signal(str)

    def __init__(self):
        super().__init__()

        self.setFixedWidth(Theme.SIDEBAR_WIDTH)

        self.setStyleSheet(f"""
            background: {Theme.SIDEBAR};
        """)

        self.buttons = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("MarkaAI")
        title.setStyleSheet("""
            color: white;
            font-size: 24px;
            font-weight: bold;
            padding: 20px;
        """)

        layout.addWidget(title)

        self.create_button(layout, "Dashboard")
        self.create_button(layout, "PDF Fatura")
        self.create_button(layout, "Mizan Analizi")
        self.create_button(layout, "AI Analiz")
        self.create_button(layout, "Aktarım")
        self.create_button(layout, "Belgeler")
        self.create_button(layout, "Ayarlar")

        layout.addStretch()

        version = QLabel("v0.1")
        version.setStyleSheet("""
            color: #94A3B8;
            padding: 20px;
        """)

        layout.addWidget(version)

        # Program açıldığında Dashboard seçili gelsin
        if self.buttons:
            self.set_active_button(self.buttons[0])

    def create_button(self, layout, text):

        button = QPushButton(text)
        button.setCheckable(True)
        button.setMinimumHeight(46)

        button.setStyleSheet(f"""
            QPushButton {{
                background: #334155;
                color: white;
                border: none;
                border-radius: 8px;
                text-align: left;
                padding-left: 20px;
                font-size: 14px;
            }}

            QPushButton:hover {{
                background: {Theme.PRIMARY};
            }}

            QPushButton:checked {{
                background: {Theme.PRIMARY};
            }}

            QPushButton:pressed {{
                background: #1D4ED8;
            }}
        """)

        button.clicked.connect(
            lambda checked=False, b=button: self.set_active_button(b)
        )

        button.clicked.connect(
            lambda checked=False, t=text: self.page_changed.emit(t)
        )

        layout.addWidget(button)
        self.buttons.append(button)

    def set_active_button(self, active_button):
        for button in self.buttons:
            button.setChecked(button is active_button)