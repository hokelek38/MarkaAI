from pathlib import Path

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

from services.accounting_service import AccountingService
from services.pdf_service import PdfService
from ui.theme import Theme


class PdfPage(QWidget):

    def __init__(self):
        super().__init__()

        self.selected_file = None
        self.invoice_data = None
        self.pdf_service = PdfService()
        self.accounting_service = AccountingService()

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
            "PDF faturanızı seçin. MarkaAI temel fatura bilgilerini otomatik çıkarsın."
        )
        subtitle.setStyleSheet(f"""
            font-size: {Theme.NORMAL}px;
            color: {Theme.SUBTEXT};
        """)

        upload_frame = QFrame()
        upload_frame.setMinimumHeight(240)
        upload_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 2px dashed #CBD5E1;
                border-radius: 14px;
            }
        """)

        upload_layout = QVBoxLayout(upload_frame)
        upload_layout.setContentsMargins(30, 30, 30, 30)
        upload_layout.setSpacing(14)
        upload_layout.setAlignment(Qt.AlignCenter)

        upload_icon = QLabel("📄")
        upload_icon.setAlignment(Qt.AlignCenter)
        upload_icon.setStyleSheet("""
            font-size: 48px;
            border: none;
        """)

        upload_title = QLabel("PDF faturanızı seçin")
        upload_title.setAlignment(Qt.AlignCenter)
        upload_title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #1F2937;
            border: none;
        """)

        upload_description = QLabel(
            "Firma, tarih, fatura numarası, KDV ve toplam tutar otomatik okunacaktır."
        )
        upload_description.setAlignment(Qt.AlignCenter)
        upload_description.setWordWrap(True)
        upload_description.setStyleSheet("""
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
        upload_layout.addWidget(upload_description)
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
        information_layout.setSpacing(12)

        information_title = QLabel("Fatura Bilgileri")
        information_title.setStyleSheet("""
            font-size: 17px;
            font-weight: bold;
            color: #1F2937;
            border: none;
        """)

        self.file_label = QLabel("Dosya: Henüz PDF seçilmedi")
        self.page_count_label = QLabel("Sayfa Sayısı: -")
        self.invoice_number_label = QLabel("Fatura No: -")
        self.date_label = QLabel("Fatura Tarihi: -")
        self.company_label = QLabel("Satıcı: -")
        self.tax_number_label = QLabel("Satıcı VKN / TCKN: -")
        self.buyer_label = QLabel("Alıcı: -")
        self.subtotal_label = QLabel("Mal Hizmet Toplamı: -")
        self.vat_label = QLabel("Hesaplanan KDV: -")
        self.total_label = QLabel("Genel Toplam: -")
        self.payable_label = QLabel("Ödenecek Tutar: -")

        information_labels = [
            self.file_label,
            self.page_count_label,
            self.invoice_number_label,
            self.date_label,
            self.company_label,
            self.tax_number_label,
            self.buyer_label,
            self.subtotal_label,
            self.vat_label,
            self.total_label,
            self.payable_label,
        ]

        for label in information_labels:
            label.setWordWrap(True)
            label.setStyleSheet("""
                font-size: 14px;
                color: #475569;
                border: none;
                padding: 2px;
            """)

        information_layout.addWidget(information_title)
        information_layout.addSpacing(5)

        for label in information_labels:
            information_layout.addWidget(label)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.analyze_button = QPushButton("🤖 Muhasebe Analizine Geç")
        self.analyze_button.setMinimumHeight(48)
        self.analyze_button.setFixedWidth(250)
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

            QPushButton:pressed {
                background: #166534;
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
        self.reset_invoice_information()

        file_name = Path(file_path).name
        self.file_label.setText(f"Dosya: {file_name}")

        try:
            self.invoice_data = self.pdf_service.analyze_invoice(file_path)

            self.show_invoice_information(self.invoice_data)
            self.analyze_button.setEnabled(True)

            QMessageBox.information(
                self,
                "Fatura Okundu",
                "Fatura bilgileri başarıyla çıkarıldı.",
            )

        except Exception as error:
            self.selected_file = None
            self.invoice_data = None
            self.analyze_button.setEnabled(False)

            QMessageBox.critical(
                self,
                "PDF Okuma Hatası",
                f"PDF okunurken bir hata oluştu:\n\n{error}",
            )

    def show_invoice_information(self, data):
        self.file_label.setText(
            f"Dosya: {data.get('file_name', '-')}"
        )

        self.page_count_label.setText(
            f"Sayfa Sayısı: {data.get('page_count', '-')}"
        )

        self.invoice_number_label.setText(
            f"Fatura No: {data.get('invoice_number', '-')}"
        )

        self.date_label.setText(
            f"Fatura Tarihi: {data.get('invoice_date', '-')}"
        )

        self.company_label.setText(
            f"Satıcı: {data.get('seller_name', '-')}"
        )

        self.tax_number_label.setText(
            f"Satıcı VKN / TCKN: {data.get('seller_tax_number', '-')}"
        )

        self.buyer_label.setText(
            f"Alıcı: {data.get('buyer_name', '-')}"
        )

        self.subtotal_label.setText(
            f"Mal Hizmet Toplamı: {data.get('subtotal', '-')}"
        )

        self.vat_label.setText(
            f"Hesaplanan KDV: {data.get('vat_amount', '-')}"
        )

        self.total_label.setText(
            f"Genel Toplam: {data.get('total_amount', '-')}"
        )

        self.payable_label.setText(
            f"Ödenecek Tutar: {data.get('payable_amount', '-')}"
        )

    def reset_invoice_information(self):
        self.page_count_label.setText("Sayfa Sayısı: -")
        self.invoice_number_label.setText("Fatura No: -")
        self.date_label.setText("Fatura Tarihi: -")
        self.company_label.setText("Satıcı: -")
        self.tax_number_label.setText("Satıcı VKN / TCKN: -")
        self.buyer_label.setText("Alıcı: -")
        self.subtotal_label.setText("Mal Hizmet Toplamı: -")
        self.vat_label.setText("Hesaplanan KDV: -")
        self.total_label.setText("Genel Toplam: -")
        self.payable_label.setText("Ödenecek Tutar: -")
        self.analyze_button.setEnabled(False)

    def analyze_pdf(self):
        if not self.selected_file or not self.invoice_data:
            QMessageBox.warning(
                self,
                "Fatura Seçilmedi",
                "Lütfen önce bir PDF faturası seçin.",
            )
            return

        try:
            accounting_data = self.accounting_service.suggest_accounts(
                self.invoice_data
            )

            message_lines = [
                "MUHASEBE FİŞİ ÖNERİSİ",
                "",
                "BORÇ",
            ]

            for entry in accounting_data["debit_entries"]:
                message_lines.append(
                    f"{entry['account_code']} "
                    f"{entry['account_name']} — {entry['amount']}"
                )

            message_lines.extend([
                "",
                "ALACAK",
            ])

            for entry in accounting_data["credit_entries"]:
                message_lines.append(
                    f"{entry['account_code']} "
                    f"{entry['account_name']} — {entry['amount']}"
                )

            message_lines.extend([
                "",
                "Öneri Gerekçesi:",
                accounting_data["reason"],
            ])

            QMessageBox.information(
                self,
                "Muhasebe Hesap Önerisi",
                "\n".join(message_lines),
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Muhasebe Analizi Hatası",
                f"Muhasebe önerisi oluşturulurken hata oluştu:\n\n{error}",
            )