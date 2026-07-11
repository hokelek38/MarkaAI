from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)

from ui.theme import Theme


class AccountingPage(QWidget):

    def __init__(self):
        super().__init__()

        self.invoice_data = None
        self.accounting_data = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(18)

        title = QLabel("Muhasebe Analizi")
        title.setStyleSheet(f"""
            font-size: {Theme.TITLE}px;
            font-weight: bold;
            color: {Theme.TEXT};
        """)

        subtitle = QLabel(
            "MarkaAI tarafından hazırlanan muhasebe fiş önerisini kontrol edin."
        )
        subtitle.setStyleSheet(f"""
            font-size: {Theme.NORMAL}px;
            color: {Theme.SUBTEXT};
        """)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(18)

        invoice_frame = self.create_invoice_frame()
        accounting_frame = self.create_accounting_frame()

        content_layout.addWidget(invoice_frame, 1)
        content_layout.addWidget(accounting_frame, 2)

        main_layout.addLayout(content_layout)

        bottom_layout = QHBoxLayout()

        self.confidence_label = QLabel("Güven Oranı: -")
        self.confidence_label.setStyleSheet("""
            font-size: 14px;
            font-weight: bold;
            color: #475569;
        """)

        self.edit_button = QPushButton("Hesabı Değiştir")
        self.edit_button.setMinimumHeight(46)
        self.edit_button.setFixedWidth(170)
        self.edit_button.setCursor(Qt.PointingHandCursor)
        self.edit_button.clicked.connect(self.edit_accounts)

        self.edit_button.setStyleSheet("""
            QPushButton {
                background: white;
                color: #2563EB;
                border: 1px solid #2563EB;
                border-radius: 9px;
                font-size: 14px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #EFF6FF;
            }
        """)

        self.create_voucher_button = QPushButton("Fişi Oluştur")
        self.create_voucher_button.setMinimumHeight(46)
        self.create_voucher_button.setFixedWidth(170)
        self.create_voucher_button.setCursor(Qt.PointingHandCursor)
        self.create_voucher_button.clicked.connect(self.create_voucher)

        self.create_voucher_button.setStyleSheet("""
            QPushButton {
                background: #16A34A;
                color: white;
                border: none;
                border-radius: 9px;
                font-size: 14px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #15803D;
            }

            QPushButton:pressed {
                background: #166534;
            }
        """)

        bottom_layout.addWidget(self.confidence_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.edit_button)
        bottom_layout.addWidget(self.create_voucher_button)

        main_layout.addLayout(bottom_layout)

    def create_invoice_frame(self):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        title = QLabel("Fatura Bilgileri")
        title.setStyleSheet("""
            font-size: 17px;
            font-weight: bold;
            color: #1F2937;
            border: none;
        """)

        self.invoice_number_label = QLabel("Fatura No: -")
        self.invoice_date_label = QLabel("Tarih: -")
        self.seller_label = QLabel("Satıcı: -")
        self.buyer_label = QLabel("Alıcı: -")
        self.subtotal_label = QLabel("Mal Hizmet Toplamı: -")
        self.vat_label = QLabel("KDV: -")
        self.total_label = QLabel("Genel Toplam: -")

        labels = [
            self.invoice_number_label,
            self.invoice_date_label,
            self.seller_label,
            self.buyer_label,
            self.subtotal_label,
            self.vat_label,
            self.total_label,
        ]

        layout.addWidget(title)
        layout.addSpacing(6)

        for label in labels:
            label.setWordWrap(True)
            label.setStyleSheet("""
                font-size: 14px;
                color: #475569;
                border: none;
                padding: 3px;
            """)
            layout.addWidget(label)

        layout.addStretch()

        return frame

    def create_accounting_frame(self):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        title = QLabel("Muhasebe Fişi Önerisi")
        title.setStyleSheet("""
            font-size: 17px;
            font-weight: bold;
            color: #1F2937;
            border: none;
        """)

        self.account_table = QTableWidget()
        self.account_table.setColumnCount(4)
        self.account_table.setHorizontalHeaderLabels(
            ["Tür", "Hesap Kodu", "Hesap Adı", "Tutar"]
        )
        self.account_table.setAlternatingRowColors(True)
        self.account_table.setEditTriggers(
            QTableWidget.NoEditTriggers
        )
        self.account_table.verticalHeader().setVisible(False)
        self.account_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.account_table.setStyleSheet("""
            QTableWidget {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                gridline-color: #E5E7EB;
                font-size: 13px;
            }

            QHeaderView::section {
                background: #F8FAFC;
                color: #334155;
                font-weight: bold;
                border: none;
                border-bottom: 1px solid #E5E7EB;
                padding: 8px;
            }
        """)

        reason_title = QLabel("Öneri Gerekçesi")
        reason_title.setStyleSheet("""
            font-size: 15px;
            font-weight: bold;
            color: #1F2937;
            border: none;
        """)

        self.reason_label = QLabel(
            "Henüz muhasebe analizi yapılmadı."
        )
        self.reason_label.setWordWrap(True)
        self.reason_label.setStyleSheet("""
            background: #F8FAFC;
            color: #475569;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            padding: 12px;
            font-size: 13px;
        """)

        layout.addWidget(title)
        layout.addWidget(self.account_table)
        layout.addWidget(reason_title)
        layout.addWidget(self.reason_label)

        return frame

    def load_analysis(self, invoice_data, accounting_data):
        self.invoice_data = invoice_data
        self.accounting_data = accounting_data

        self.invoice_number_label.setText(
            f"Fatura No: {invoice_data.get('invoice_number', '-')}"
        )
        self.invoice_date_label.setText(
            f"Tarih: {invoice_data.get('invoice_date', '-')}"
        )
        self.seller_label.setText(
            f"Satıcı: {invoice_data.get('seller_name', '-')}"
        )
        self.buyer_label.setText(
            f"Alıcı: {invoice_data.get('buyer_name', '-')}"
        )
        self.subtotal_label.setText(
            f"Mal Hizmet Toplamı: {invoice_data.get('subtotal', '-')}"
        )
        self.vat_label.setText(
            f"KDV: {invoice_data.get('vat_amount', '-')}"
        )
        self.total_label.setText(
            f"Genel Toplam: {invoice_data.get('total_amount', '-')}"
        )

        entries = []

        for entry in accounting_data.get("debit_entries", []):
            entries.append({
                "type": "Borç",
                **entry,
            })

        for entry in accounting_data.get("credit_entries", []):
            entries.append({
                "type": "Alacak",
                **entry,
            })

        self.account_table.setRowCount(len(entries))

        for row, entry in enumerate(entries):
            type_item = QTableWidgetItem(entry.get("type", "-"))
            code_item = QTableWidgetItem(entry.get("account_code", "-"))
            name_item = QTableWidgetItem(entry.get("account_name", "-"))
            amount_item = QTableWidgetItem(entry.get("amount", "-"))

            self.account_table.setItem(row, 0, type_item)
            self.account_table.setItem(row, 1, code_item)
            self.account_table.setItem(row, 2, name_item)
            self.account_table.setItem(row, 3, amount_item)

        self.reason_label.setText(
            accounting_data.get(
                "reason",
                "Öneri gerekçesi bulunamadı."
            )
        )

        confidence = accounting_data.get("confidence", 90)
        self.confidence_label.setText(
            f"Güven Oranı: %{confidence}"
        )

    def edit_accounts(self):
        QMessageBox.information(
            self,
            "Hesap Düzenleme",
            "Hesap değiştirme özelliği sonraki adımda eklenecek.",
        )

    def create_voucher(self):
        if not self.accounting_data:
            QMessageBox.warning(
                self,
                "Analiz Bulunamadı",
                "Önce bir muhasebe analizi oluşturulmalıdır.",
            )
            return

        QMessageBox.information(
            self,
            "Fiş Oluşturuldu",
            "Muhasebe fişi taslak olarak oluşturuldu.",
        )