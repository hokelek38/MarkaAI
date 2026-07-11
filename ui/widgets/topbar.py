from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout

from ui.theme import Theme


class TopBar(QWidget):

    def __init__(self):
        super().__init__()

        self.setFixedHeight(60)

        layout = QHBoxLayout(self)

        title = QLabel("Ana Menü")

        title.setStyleSheet(f"""
            font-size:20px;
            font-weight:bold;
            color:{Theme.TEXT};
        """)

        layout.addWidget(title)
        layout.addStretch()