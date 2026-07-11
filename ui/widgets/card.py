from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class Card(QFrame):

    clicked = Signal()

    def __init__(self, title, description):
        super().__init__()

        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(280, 180)
        self.setMaximumWidth(320)

        self.setStyleSheet("""
            QFrame{
                background:white;
                border:1px solid #E5E7EB;
                border-radius:12px;
            }

            QFrame:hover{
                border:2px solid #2563EB;
            }

            QLabel#title{
                font-size:18px;
                font-weight:bold;
                color:#1F2937;
            }

            QLabel#description{
                font-size:13px;
                color:#6B7280;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20,20,20,20)
        layout.setSpacing(15)

        title_label = QLabel(title)
        title_label.setObjectName("title")

        description_label = QLabel(description)
        description_label.setObjectName("description")
        description_label.setWordWrap(True)

        layout.addStretch()
        layout.addWidget(title_label)
        layout.addWidget(description_label)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)