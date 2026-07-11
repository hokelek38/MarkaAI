from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QFileDialog,
    QMessageBox,
)

from ui.theme import Theme


class PdfPage(QWidget):

    def __init__(self):
        super().__init__()

        self.selected_file = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(20)

        title = QLabel("PDF Fatura Aktar")
        title.setStyleSheet(f"""
            font-size: {Theme.TITLE}px;
            font-weight: bold;
            color: {Theme.TEXT};
        """)

        subtitle = QLabel(
            "PDF'nizi sürükleyip bırakın. Muhasebe fişini yapay zekâ oluştursun."
        )
        subtitle.setStyleSheet(f"""
            font-size: {Theme.NORMAL}px;
            color: {Theme.SUBTEXT};
        """)

        upload_frame = QFrame()
        upload_frame.setMinimumHeight(280)
        upload_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 2px dashed #CBD5E1;
                border-radius: 14px;
            }
        """)

        upload_layout = QVBoxLayout(upload_frame)
        upload_layout.setContentsMargins(30, 30, 30, 30)
        upload_layout.setSpacing(15)
        upload_layout.setAlignment(Qt.AlignCenter)

        upload_icon = QLabel("📄")
        upload_icon.setAlignment(Qt.AlignCenter)
        upload_icon.setStyleSheet("""
            font-size: 48px;
            border: none;
        """)

        upload_title = QLabel("PDF dosyasını buraya sürükleyin")
        upload_title.setAlignment(Qt.AlignCenter)
        upload_title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #1F2937;
            border: none;
        """)

        upload_or = QLabel("veya")
        upload_or.setAlignment(Qt.AlignCenter)
        upload_or.setStyleSheet("""
            font-size: 13px;
            color: #64748B;
            border: none;
        """)

        select_button = QPushButton("PDF Seç")
        select_button.setFixedWidth(180)
        select_button.setMinimumHeight(48)
        select_button.setCursor(Qt.PointingHandCursor)
        select_button.clicked.connect(self.select_pdf)

        select_button.setStyleSheet(f"""
            QPushButton {{
                background: {Theme.PRIMARY};
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 15px;
                font-weight: bold;
            }}

            QPushButton:hover {{
                background: #1D4ED8;
            }}

            QPushButton:pressed {{
                background: #1E40AF;
            }}
        """)

        upload_layout.addStretch()
        upload_layout.addWidget(upload_icon)
        upload_layout.addWidget(upload_title)
        upload_layout.addWidget(upload_or)
        upload_layout.addWidget(select_button, alignment=Qt.AlignCenter)
        upload_layout.addStretch()

        information_frame = QFrame()
        information_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
        """)

        information_layout = QVBoxLayout(information_frame)
        information_layout.setContentsMargins(24, 20, 24, 20)
        information_layout.setSpacing(14)

        information_title = QLabel("Dosya Bilgileri")
        information_title.setStyleSheet("""
            font-size: 17px;
            font-weight: bold;
            color: #1F2937;
            border: none;
        """)

        self.file_label = QLabel("Dosya: Henüz PDF seçilmedi")
        self.company_label = QLabel("Firma: -")
        self.date_label = QLabel("Tarih: -")
        self.total_label = QLabel("Toplam Tutar: -")
        self.page_count_label = QLabel("Sayfa Sayısı: -")

        information_labels = [
            self.file_label,
            self.company_label,
            self.date_label,
            self.total_label,
            self.page_count_label,
        ]

        for label in information_labels:
            label.setStyleSheet("""
                font-size: 14px;
                color: #475569;
                border: none;
            """)

        information_layout.addWidget(information_title)
        information_layout.addSpacing(5)

        for label in information_labels:
            information_layout.addWidget(label)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.analyze_button = QPushButton("🤖 AI ile Analiz Et")
        self.analyze_button.setMinimumHeight(48)
        self.analyze_button.setFixedWidth(220)
        self.analyze_button.setEnabled(False)
        self.analyze_button.clicked.connect(self.analyze_pdf)

        self.analyze_button.setStyleSheet("""
            QPushButton {
                background: #16A34A;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #15803D;
            }

            QPushButton:disabled {
                background: #CBD5E1;
                color: #64748B;
            }
        """)

        button_layout.addWidget(self.analyze_button)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addWidget(upload_frame)
        main_layout.addWidget(information_frame)
        main_layout.addLayout(button_layout)
        main_layout.addStretch()

    def select_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "PDF Fatura Seç",
            "",
            "PDF Dosyaları (*.pdf)",
        )

        if not file_path:
            return

        self.selected_file = file_path

        file_name = file_path.split("/")[-1]
        self.file_label.setText(f"Dosya: {file_name}")
        self.analyze_button.setEnabled(True)

    def analyze_pdf(self):
        if not self.selected_file:
            QMessageBox.warning(
                self,
                "PDF Seçilmedi",
                "Lütfen önce bir PDF dosyası seçin.",
            )
            return

        QMessageBox.information(
            self,
            "AI Analizi",
            "AI analiz özelliği sonraki adımda eklenecek.",
        )