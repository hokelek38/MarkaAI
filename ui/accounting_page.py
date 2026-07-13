from pathlib import Path

import pymupdf

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import (
    QDesktopServices,
    QImage,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.voucher_engine import VoucherEngine


class AccountingPage(QWidget):
    """
    MarkaAI muhasebe analiz ekranı.

    Bölümler:
    - PDF önizleme
    - Muhasebe fişi
    - Karar, mevzuat dayanağı ve uyarılar
    - Mali müşavir onayı
    """

    voucher_approved = Signal(dict)
    line_usage_review_submitted = Signal(dict)

    def __init__(self):
        super().__init__()

        self.voucher_data = None
        self.validation_result = {}
        self.line_usage_review_data = {}
        self.line_usage_review_invoice = {}
        self.line_usage_review_company = {}
        self.line_usage_combo_boxes = []
        self.voucher_engine = VoucherEngine()

        self.pdf_document = None
        self.pdf_path = None
        self.current_pdf_page = 0
        self.current_pdf_pixmap = None

        self.focus_mode_enabled = False
        self.normal_splitter_sizes = [
            380,
            650,
            330,
        ]

        self.build_ui()

    def build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        root_layout.setSpacing(12)

        root_layout.addLayout(
            self.create_header()
        )

        self.main_splitter = QSplitter(
            Qt.Horizontal
        )
        self.main_splitter.setChildrenCollapsible(
            True
        )
        self.main_splitter.setHandleWidth(6)
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background: #DCE4EE;
                border-radius: 3px;
            }

            QSplitter::handle:hover {
                background: #94A3B8;
            }
        """)

        self.pdf_panel = self.create_pdf_panel()
        self.voucher_panel = (
            self.create_voucher_panel()
        )
        self.review_panel = (
            self.create_review_panel()
        )

        self.main_splitter.addWidget(
            self.pdf_panel
        )
        self.main_splitter.addWidget(
            self.voucher_panel
        )
        self.main_splitter.addWidget(
            self.review_panel
        )

        self.main_splitter.setStretchFactor(
            0,
            3,
        )
        self.main_splitter.setStretchFactor(
            1,
            5,
        )
        self.main_splitter.setStretchFactor(
            2,
            3,
        )

        self.main_splitter.setSizes(
            self.normal_splitter_sizes
        )

        root_layout.addWidget(
            self.main_splitter,
            1,
        )

        root_layout.addWidget(
            self.create_bottom_bar()
        )

    def create_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(
            4,
            0,
            4,
            0,
        )

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)

        title = QLabel("Fatura Analizi")
        title.setStyleSheet("""
            color: #172033;
            font-size: 24px;
            font-weight: 800;
        """)

        subtitle = QLabel(
            "Belgeyi, muhasebe fişini ve kontrol "
            "sonuçlarını birlikte inceleyin."
        )
        subtitle.setStyleSheet("""
            color: #64748B;
            font-size: 12px;
        """)

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        self.header_status_label = QLabel(
            "Fiş yüklenmedi"
        )
        self.header_status_label.setAlignment(
            Qt.AlignCenter
        )
        self.header_status_label.setMinimumHeight(
            34
        )
        self.header_status_label.setStyleSheet("""
            background: #E2E8F0;
            color: #64748B;
            border-radius: 17px;
            padding: 0 16px;
            font-size: 11px;
            font-weight: 700;
        """)

        layout.addLayout(title_layout)
        layout.addStretch()
        layout.addWidget(
            self.header_status_label
        )

        return layout

    def create_pdf_panel(self) -> QFrame:
        frame = self.create_card()
        frame.setMinimumWidth(290)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            14,
            14,
            14,
            14,
        )
        layout.setSpacing(10)

        header_layout = QHBoxLayout()

        title = QLabel("PDF Görüntüsü")
        title.setStyleSheet(
            self.section_title_style()
        )

        self.open_pdf_button = QPushButton(
            "Dışarıda Aç"
        )
        self.open_pdf_button.setFixedHeight(30)
        self.open_pdf_button.setEnabled(False)
        self.open_pdf_button.setCursor(
            Qt.PointingHandCursor
        )
        self.open_pdf_button.clicked.connect(
            self.open_pdf_external
        )
        self.open_pdf_button.setStyleSheet(
            self.secondary_button_style()
        )

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(
            self.open_pdf_button
        )

        layout.addLayout(header_layout)

        self.pdf_information_label = QLabel(
            "PDF dosyası yüklenmedi."
        )
        self.pdf_information_label.setWordWrap(
            True
        )
        self.pdf_information_label.setStyleSheet("""
            color: #64748B;
            font-size: 11px;
        """)

        layout.addWidget(
            self.pdf_information_label
        )

        self.pdf_scroll = QScrollArea()
        self.pdf_scroll.setWidgetResizable(True)
        self.pdf_scroll.setAlignment(
            Qt.AlignCenter
        )
        self.pdf_scroll.setFrameShape(
            QFrame.NoFrame
        )
        self.pdf_scroll.setStyleSheet("""
            QScrollArea {
                background: #E9EEF5;
                border: 1px solid #D7E0EB;
                border-radius: 8px;
            }

            QScrollBar:vertical {
                background: #EEF2F7;
                width: 9px;
            }

            QScrollBar::handle:vertical {
                background: #AAB8C8;
                border-radius: 4px;
                min-height: 30px;
            }

            QScrollBar:horizontal {
                background: #EEF2F7;
                height: 9px;
            }

            QScrollBar::handle:horizontal {
                background: #AAB8C8;
                border-radius: 4px;
            }
        """)

        self.pdf_preview_label = QLabel(
            "PDF önizlemesi burada gösterilecek."
        )
        self.pdf_preview_label.setAlignment(
            Qt.AlignCenter
        )
        self.pdf_preview_label.setWordWrap(True)
        self.pdf_preview_label.setMinimumSize(
            250,
            400,
        )
        self.pdf_preview_label.setStyleSheet("""
            background: #F8FAFC;
            color: #94A3B8;
            font-size: 12px;
            padding: 20px;
        """)

        self.pdf_scroll.setWidget(
            self.pdf_preview_label
        )

        layout.addWidget(
            self.pdf_scroll,
            1,
        )

        navigation_layout = QHBoxLayout()

        self.previous_page_button = QPushButton(
            "‹ Önceki"
        )
        self.next_page_button = QPushButton(
            "Sonraki ›"
        )

        self.previous_page_button.setEnabled(
            False
        )
        self.next_page_button.setEnabled(False)

        self.previous_page_button.clicked.connect(
            self.show_previous_pdf_page
        )
        self.next_page_button.clicked.connect(
            self.show_next_pdf_page
        )

        self.previous_page_button.setStyleSheet(
            self.secondary_button_style()
        )
        self.next_page_button.setStyleSheet(
            self.secondary_button_style()
        )

        self.pdf_page_label = QLabel(
            "Sayfa - / -"
        )
        self.pdf_page_label.setAlignment(
            Qt.AlignCenter
        )
        self.pdf_page_label.setStyleSheet("""
            color: #475569;
            font-size: 11px;
            font-weight: 700;
        """)

        navigation_layout.addWidget(
            self.previous_page_button
        )
        navigation_layout.addStretch()
        navigation_layout.addWidget(
            self.pdf_page_label
        )
        navigation_layout.addStretch()
        navigation_layout.addWidget(
            self.next_page_button
        )

        layout.addLayout(navigation_layout)

        return frame

    def create_voucher_panel(self) -> QFrame:
        frame = self.create_card()
        frame.setMinimumWidth(430)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            16,
            14,
            16,
            14,
        )
        layout.setSpacing(10)

        header_layout = QHBoxLayout()

        title = QLabel("Muhasebe Fişi")
        title.setStyleSheet(
            self.section_title_style()
        )

        self.focus_button = QPushButton(
            "⛶ Fişi Genişlet"
        )
        self.focus_button.setFixedHeight(32)
        self.focus_button.setCursor(
            Qt.PointingHandCursor
        )
        self.focus_button.clicked.connect(
            self.toggle_voucher_focus
        )
        self.focus_button.setStyleSheet(
            self.secondary_button_style()
        )

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(
            self.focus_button
        )

        layout.addLayout(header_layout)

        document_frame = QFrame()
        document_frame.setStyleSheet("""
            QFrame {
                background: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
        """)

        document_layout = QHBoxLayout(
            document_frame
        )
        document_layout.setContentsMargins(
            12,
            9,
            12,
            9,
        )
        document_layout.setSpacing(18)

        self.document_number_label = QLabel(
            "Belge No: -"
        )
        self.document_date_label = QLabel(
            "Tarih: -"
        )
        self.transaction_label = QLabel(
            "İşlem: -"
        )
        self.counterparty_label = QLabel(
            "Cari: -"
        )

        for label in [
            self.document_number_label,
            self.document_date_label,
            self.transaction_label,
            self.counterparty_label,
        ]:
            label.setWordWrap(True)
            label.setStyleSheet("""
                color: #475569;
                font-size: 11px;
                border: none;
            """)

        document_layout.addWidget(
            self.document_number_label
        )
        document_layout.addWidget(
            self.document_date_label
        )
        document_layout.addWidget(
            self.transaction_label
        )
        document_layout.addWidget(
            self.counterparty_label,
            1,
        )

        layout.addWidget(document_frame)

        self.voucher_table = QTableWidget()
        self.voucher_table.setColumnCount(6)
        self.voucher_table.setHorizontalHeaderLabels([
            "Sıra",
            "Hesap Kodu",
            "Hesap Adı",
            "Borç",
            "Alacak",
            "Açıklama",
        ])
        self.voucher_table.setAlternatingRowColors(
            True
        )
        self.voucher_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )
        self.voucher_table.setSelectionMode(
            QAbstractItemView.SingleSelection
        )
        self.voucher_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        self.voucher_table.verticalHeader().setVisible(
            False
        )
        self.voucher_table.verticalHeader().setDefaultSectionSize(
            40
        )
        self.voucher_table.setShowGrid(False)
        self.voucher_table.setWordWrap(False)

        header = (
            self.voucher_table.horizontalHeader()
        )
        header.setMinimumSectionSize(65)
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeToContents,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeToContents,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.Stretch,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeToContents,
        )
        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeToContents,
        )
        header.setSectionResizeMode(
            5,
            QHeaderView.Stretch,
        )

        self.voucher_table.setStyleSheet("""
            QTableWidget {
                background: white;
                color: #243247;
                border: 1px solid #DCE4EE;
                border-radius: 8px;
                alternate-background-color: #F7F9FC;
                font-size: 12px;
                gridline-color: transparent;
            }

            QTableWidget::item {
                padding: 7px;
                border-bottom: 1px solid #EDF1F5;
            }

            QTableWidget::item:selected {
                background: #DCEBFF;
                color: #173E70;
            }

            QHeaderView::section {
                background: #EDF3F9;
                color: #334155;
                border: none;
                border-bottom: 1px solid #D8E1EC;
                padding: 9px 7px;
                font-size: 11px;
                font-weight: 800;
            }
        """)

        layout.addWidget(
            self.voucher_table,
            1,
        )

        totals_frame = QFrame()
        totals_frame.setStyleSheet("""
            QFrame {
                background: #F4F7FB;
                border: 1px solid #DCE4EE;
                border-radius: 8px;
            }
        """)

        totals_layout = QHBoxLayout(
            totals_frame
        )
        totals_layout.setContentsMargins(
            12,
            9,
            12,
            9,
        )

        self.debit_total_label = QLabel(
            "Borç: 0,00"
        )
        self.credit_total_label = QLabel(
            "Alacak: 0,00"
        )
        self.balance_status_label = QLabel(
            "Durum: -"
        )

        for label in [
            self.debit_total_label,
            self.credit_total_label,
            self.balance_status_label,
        ]:
            label.setStyleSheet("""
                color: #334155;
                font-size: 12px;
                font-weight: 800;
                border: none;
            """)

        totals_layout.addWidget(
            self.debit_total_label
        )
        totals_layout.addSpacing(20)
        totals_layout.addWidget(
            self.credit_total_label
        )
        totals_layout.addStretch()
        totals_layout.addWidget(
            self.balance_status_label
        )

        layout.addWidget(totals_frame)

        return frame

    def create_review_panel(self) -> QFrame:
        frame = self.create_card()
        frame.setMinimumWidth(270)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
        """)

        content = QWidget()
        content.setStyleSheet(
            "background: white;"
        )

        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(
            14,
            14,
            14,
            14,
        )
        content_layout.setSpacing(12)

        content_layout.addWidget(
            self.create_decision_card()
        )

        self.line_usage_review_card = (
            self.create_line_usage_review_card()
        )

        content_layout.addWidget(
            self.line_usage_review_card
        )
        content_layout.addWidget(
            self.create_legal_basis_card()
        )
        content_layout.addWidget(
            self.create_findings_card()
        )
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

        return frame

    def create_decision_card(self) -> QFrame:
        frame = self.create_information_card()

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            12,
            12,
            12,
            12,
        )
        layout.setSpacing(8)

        title = QLabel("Karar Bilgileri")
        title.setStyleSheet(
            self.section_title_style()
        )

        self.rule_label = QLabel(
            "Uygulanan kural: -"
        )
        self.confidence_label = QLabel(
            "Güven oranı: -"
        )
        self.reason_label = QLabel(
            "Gerekçe: -"
        )

        self.reason_label.setWordWrap(True)

        for label in [
            self.rule_label,
            self.confidence_label,
            self.reason_label,
        ]:
            label.setStyleSheet("""
                color: #475569;
                font-size: 11px;
                border: none;
            """)

        layout.addWidget(title)
        layout.addWidget(self.rule_label)
        layout.addWidget(
            self.confidence_label
        )
        layout.addWidget(self.reason_label)

        return frame

    def create_line_usage_review_card(
        self,
    ) -> QFrame:
        """
        Kullanım amacı belirlenemeyen kalemleri
        kullanıcıya gösterir.
        """

        frame = self.create_information_card()
        frame.setVisible(False)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            12,
            12,
            12,
            12,
        )
        layout.setSpacing(8)

        title = QLabel(
            "Kullanım Amacı Seçimi"
        )
        title.setWordWrap(True)
        title.setStyleSheet(
            self.section_title_style()
        )

        self.line_usage_information_label = QLabel(
            "Kullanım amacı belirlenemeyen "
            "kalemler burada gösterilecek."
        )
        self.line_usage_information_label.setWordWrap(
            True
        )
        self.line_usage_information_label.setStyleSheet("""
            background: #FFF7E6;
            color: #8A5A00;
            border: 1px solid #F0D18A;
            border-radius: 7px;
            padding: 9px;
            font-size: 11px;
        """)

        self.line_usage_table = QTableWidget()
        self.line_usage_table.setColumnCount(2)
        self.line_usage_table.setHorizontalHeaderLabels([
            "Fatura Kalemi",
            "Kullanım Amacı",
        ])
        self.line_usage_table.setMinimumHeight(220)
        self.line_usage_table.setMaximumHeight(360)
        self.line_usage_table.setAlternatingRowColors(
            True
        )
        self.line_usage_table.setSelectionMode(
            QAbstractItemView.NoSelection
        )
        self.line_usage_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        self.line_usage_table.verticalHeader().setVisible(
            False
        )
        self.line_usage_table.verticalHeader().setDefaultSectionSize(
            82
        )

        header = (
            self.line_usage_table.horizontalHeader()
        )
        header.setSectionResizeMode(
            0,
            QHeaderView.Stretch,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.Stretch,
        )

        self.line_usage_apply_button = QPushButton(
            "Seçimleri Uygula ve Yeniden Hesapla"
        )
        self.line_usage_apply_button.setMinimumHeight(
            40
        )
        self.line_usage_apply_button.setCursor(
            Qt.PointingHandCursor
        )
        self.line_usage_apply_button.clicked.connect(
            self.submit_line_usage_review
        )
        self.line_usage_apply_button.setStyleSheet("""
            QPushButton {
                background: #2563EB;
                color: white;
                border: none;
                border-radius: 7px;
                padding: 8px;
                font-size: 11px;
                font-weight: 800;
            }

            QPushButton:hover {
                background: #1D4ED8;
            }
        """)

        layout.addWidget(title)
        layout.addWidget(
            self.line_usage_information_label
        )
        layout.addWidget(
            self.line_usage_table
        )
        layout.addWidget(
            self.line_usage_apply_button
        )

        return frame

    def load_line_usage_review(
        self,
        *,
        analysis_result: dict,
        invoice_data: dict,
        company: dict,
    ) -> None:
        """
        Belirsiz kalemleri inceleme kartına yükler.
        """

        self.voucher_data = None
        self.validation_result = {}

        self.line_usage_review_data = dict(
            analysis_result or {}
        )
        self.line_usage_review_invoice = dict(
            invoice_data or {}
        )
        self.line_usage_review_company = dict(
            company or {}
        )

        review_data = analysis_result.get(
            "line_usage_review",
            {},
        )

        unresolved_lines = list(
            review_data.get(
                "unresolved_lines",
                [],
            )
        )

        self.line_usage_combo_boxes = []
        self.line_usage_table.clearContents()
        self.line_usage_table.setRowCount(
            len(unresolved_lines)
        )

        usage_options = [
            ("Seçiniz", ""),
            (
                "Üretimde kullanılacak",
                "production_material",
            ),
            (
                "Yeniden satılacak",
                "resale_goods",
            ),
            (
                "Hizmet üretiminde kullanılacak",
                "service_production",
            ),
            (
                "Pazarlama / satış gideri",
                "selling_expense",
            ),
            (
                "Genel yönetim gideri",
                "administrative_expense",
            ),
            (
                "Duran varlık adayı",
                "fixed_asset",
            ),
        ]

        for row, line in enumerate(
            unresolved_lines
        ):
            description = str(
                line.get(
                    "description",
                    "",
                )
                or "Açıklamasız kalem"
            )

            amount = str(
                line.get(
                    "amount",
                    "",
                )
            ).strip()

            reason = str(
                line.get(
                    "reason",
                    "",
                )
            ).strip()

            display_text = description

            if amount:
                display_text += (
                    "\nTutar: "
                    f"{self.format_amount(amount)}"
                )

            if reason:
                display_text += (
                    f"\n{reason}"
                )

            self.line_usage_table.setItem(
                row,
                0,
                QTableWidgetItem(
                    display_text
                ),
            )

            combo = QComboBox()

            for option_name, usage_code in (
                usage_options
            ):
                combo.addItem(
                    option_name,
                    usage_code,
                )

            combo.setProperty(
                "line_index",
                row,
            )
            combo.setProperty(
                "line_number",
                line.get(
                    "line_number",
                    "",
                ),
            )
            combo.setProperty(
                "description",
                description,
            )

            self.line_usage_table.setCellWidget(
                row,
                1,
                combo,
            )

            self.line_usage_combo_boxes.append(
                combo
            )

        invoice_number = (
            invoice_data.get(
                "invoice_number",
                "-",
            )
            or "-"
        )

        invoice_date = (
            invoice_data.get(
                "invoice_date",
                "-",
            )
            or "-"
        )

        counterparty = (
            invoice_data.get(
                "seller_name",
                invoice_data.get(
                    "buyer_name",
                    "-",
                ),
            )
            or "-"
        )

        self.document_number_label.setText(
            f"Belge No: {invoice_number}"
        )
        self.document_date_label.setText(
            f"Tarih: {invoice_date}"
        )
        self.transaction_label.setText(
            "İşlem: Kalem incelemesi gerekli"
        )
        self.counterparty_label.setText(
            f"Cari: {counterparty}"
        )

        self.voucher_table.setRowCount(0)

        self.debit_total_label.setText(
            "Borç: 0,00"
        )
        self.credit_total_label.setText(
            "Alacak: 0,00"
        )
        self.balance_status_label.setText(
            "⚠ Fiş Oluşturulmadı"
        )

        self.rule_label.setText(
            "Uygulanan kural: "
            "Kullanım amacı güvenlik kontrolü"
        )
        self.confidence_label.setText(
            "Güven oranı: Kesinleştirilemedi"
        )
        self.reason_label.setText(
            "Gerekçe: Kullanım amacı belirlenmeden "
            "muhasebe hesabı seçilemez."
        )

        findings = (
            list(
                analysis_result.get(
                    "errors",
                    [],
                )
            )
            + list(
                analysis_result.get(
                    "warnings",
                    [],
                )
            )
        )

        self.findings_label.setText(
            "\n".join(
                f"• {message}"
                for message in findings
            )
            if findings
            else (
                "Kullanım amacı seçimi bekleniyor."
            )
        )

        self.line_usage_information_label.setText(
            f"{len(unresolved_lines)} fatura "
            "kalemi için kullanım amacı seçilmelidir."
        )

        self.line_usage_review_card.setVisible(
            True
        )

        self.header_status_label.setText(
            "● Kullanım Amacı Bekliyor"
        )
        self.status_label.setText(
            "Durum: Fatura kalemleri "
            "kullanıcı incelemesi bekliyor"
        )

        self.approve_button.setEnabled(False)

    def submit_line_usage_review(
        self,
    ) -> None:
        """
        Kullanım amacı seçimlerini dışarı gönderir.
        """

        selections = []

        for combo in self.line_usage_combo_boxes:
            usage_code = str(
                combo.currentData()
                or ""
            ).strip()

            if not usage_code:
                QMessageBox.warning(
                    self,
                    "Eksik Seçim",
                    "Bütün kalemler için kullanım "
                    "amacı seçilmelidir.",
                )
                return

            selections.append({
                "line_index": int(
                    combo.property(
                        "line_index"
                    )
                ),
                "line_number": (
                    combo.property(
                        "line_number"
                    )
                ),
                "description": str(
                    combo.property(
                        "description"
                    )
                    or ""
                ),
                "usage": usage_code,
            })

        self.line_usage_review_submitted.emit({
            "selections": selections,
            "invoice_data": dict(
                self.line_usage_review_invoice
            ),
            "company": dict(
                self.line_usage_review_company
            ),
            "analysis_result": dict(
                self.line_usage_review_data
            ),
        })

    def create_legal_basis_card(self) -> QFrame:
        frame = self.create_information_card()

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            12,
            12,
            12,
            12,
        )
        layout.setSpacing(8)

        title = QLabel("Kanun ve Mevzuat Dayanağı")
        title.setWordWrap(True)
        title.setStyleSheet(
            self.section_title_style()
        )

        self.legal_basis_label = QLabel(
            "Doğrulanmış mevzuat dayanağı "
            "henüz bu fişe eklenmedi."
        )
        self.legal_basis_label.setWordWrap(True)
        self.legal_basis_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )
        self.legal_basis_label.setStyleSheet("""
            background: #F1F6FE;
            color: #31577F;
            border: 1px solid #D7E5F5;
            border-radius: 7px;
            padding: 10px;
            font-size: 11px;
        """)

        layout.addWidget(title)
        layout.addWidget(
            self.legal_basis_label
        )

        return frame

    def create_findings_card(self) -> QFrame:
        frame = self.create_information_card()

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(
            12,
            12,
            12,
            12,
        )
        layout.setSpacing(8)

        title = QLabel("Tespitler ve Uyarılar")
        title.setStyleSheet(
            self.section_title_style()
        )

        self.findings_label = QLabel(
            "Henüz kontrol sonucu bulunmuyor."
        )
        self.findings_label.setWordWrap(True)
        self.findings_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )
        self.findings_label.setStyleSheet("""
            background: #FFF9EB;
            color: #805D13;
            border: 1px solid #F2D995;
            border-radius: 7px;
            padding: 10px;
            font-size: 11px;
        """)

        layout.addWidget(title)
        layout.addWidget(
            self.findings_label
        )

        return frame

    def create_bottom_bar(self) -> QFrame:
        frame = QFrame()
        frame.setFixedHeight(62)
        frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #DCE4EE;
                border-radius: 10px;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(
            15,
            9,
            12,
            9,
        )
        layout.setSpacing(10)

        self.status_label = QLabel(
            "Durum: Fiş yüklenmedi"
        )
        self.status_label.setStyleSheet("""
            color: #64748B;
            font-size: 12px;
            font-weight: 700;
            border: none;
        """)

        self.reanalyze_button = QPushButton(
            "Analizi Yenile"
        )
        self.reanalyze_button.setFixedSize(
            135,
            42,
        )
        self.reanalyze_button.setCursor(
            Qt.PointingHandCursor
        )
        self.reanalyze_button.clicked.connect(
            self.show_reanalysis_information
        )
        self.reanalyze_button.setStyleSheet(
            self.secondary_button_style()
        )

        self.approve_button = QPushButton(
            "✓ Fişi Onayla"
        )
        self.approve_button.setFixedSize(
            150,
            42,
        )
        self.approve_button.setEnabled(False)
        self.approve_button.setCursor(
            Qt.PointingHandCursor
        )
        self.approve_button.clicked.connect(
            self.approve_voucher
        )
        self.approve_button.setStyleSheet("""
            QPushButton {
                background: #159A55;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 12px;
                font-weight: 800;
            }

            QPushButton:hover {
                background: #118247;
            }

            QPushButton:pressed {
                background: #0D6B3A;
            }

            QPushButton:disabled {
                background: #CBD5E1;
                color: #7B8A9C;
            }
        """)

        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(
            self.reanalyze_button
        )
        layout.addWidget(
            self.approve_button
        )

        return frame

    def load_voucher(
        self,
        voucher_data: dict,
        validation_result: dict | None = None,
    ):
        """
        MSV fişini ve doğrulama sonucunu ekrana yükler.
        """

        if hasattr(
            self,
            "line_usage_review_card",
        ):
            self.line_usage_review_card.setVisible(
                False
            )

        self.voucher_data = voucher_data
        self.validation_result = (
            validation_result or {}
        )

        voucher = voucher_data.get(
            "voucher",
            {},
        )

        if not voucher:
            QMessageBox.critical(
                self,
                "Fiş Hatası",
                "Geçerli bir MSV fişi bulunamadı.",
            )
            return

        document = voucher.get(
            "document",
            {},
        )
        transaction = voucher.get(
            "transaction",
            {},
        )
        counterparty = voucher.get(
            "counterparty",
            {},
        )
        decision = voucher.get(
            "decision",
            {},
        )
        totals = voucher.get(
            "totals",
            {},
        )

        self.document_number_label.setText(
            "Belge No: "
            f"{document.get('document_number', '-')}"
        )
        self.document_date_label.setText(
            "Tarih: "
            f"{document.get('document_date', '-')}"
        )
        self.transaction_label.setText(
            "İşlem: "
            f"{transaction.get('transaction_name', '-')}"
        )
        self.counterparty_label.setText(
            "Cari: "
            f"{counterparty.get('title', '-')}"
        )

        self.rule_label.setText(
            "Uygulanan kural: "
            f"{decision.get('rule_id', '-') or '-'}"
        )
        self.confidence_label.setText(
            "Güven oranı: "
            f"%{decision.get('confidence', 0)}"
        )
        self.reason_label.setText(
            "Gerekçe: "
            f"{decision.get('reason', '-') or '-'}"
        )

        self.load_lines(
            voucher.get("lines", [])
        )

        debit_total = totals.get(
            "debit_total",
            "0.00",
        )
        credit_total = totals.get(
            "credit_total",
            "0.00",
        )

        self.debit_total_label.setText(
            f"Borç: {self.format_amount(debit_total)}"
        )
        self.credit_total_label.setText(
            f"Alacak: {self.format_amount(credit_total)}"
        )

        is_balanced = (
            totals.get("is_balanced") is True
        )

        if is_balanced:
            self.balance_status_label.setText(
                "✓ Fiş Dengeli"
            )
            self.balance_status_label.setStyleSheet("""
                color: #159A55;
                font-size: 12px;
                font-weight: 800;
                border: none;
            """)
        else:
            self.balance_status_label.setText(
                "⚠ Fiş Dengesiz"
            )
            self.balance_status_label.setStyleSheet("""
                color: #DC2626;
                font-size: 12px;
                font-weight: 800;
                border: none;
            """)

        self.show_legal_basis(decision)
        self.show_validation_result(
            self.validation_result,
            decision,
        )
        self.load_pdf_from_document(document)

        approved = decision.get(
            "approved",
            False,
        )

        visible_errors = (
            self.get_visible_validation_errors()
        )

        if approved:
            self.set_approved_state()
        else:
            self.header_status_label.setText(
                "● Onay Bekliyor"
            )
            self.header_status_label.setStyleSheet("""
                background: #FFF4DB;
                color: #A66A00;
                border-radius: 17px;
                padding: 0 16px;
                font-size: 11px;
                font-weight: 700;
            """)

            self.status_label.setText(
                "Durum: Mali müşavir onayı bekleniyor"
            )
            self.status_label.setStyleSheet("""
                color: #B7790B;
                font-size: 12px;
                font-weight: 700;
                border: none;
            """)

            self.approve_button.setText(
                "✓ Fişi Onayla"
            )
            self.approve_button.setEnabled(
                is_balanced
                and not visible_errors
            )

    def load_lines(
        self,
        lines: list[dict],
    ):
        self.voucher_table.setRowCount(
            len(lines)
        )

        for row, line in enumerate(lines):
            values = [
                str(
                    line.get(
                        "line_number",
                        row + 1,
                    )
                ),
                line.get(
                    "account_code",
                    "-",
                ),
                line.get(
                    "account_name",
                    "-",
                ),
                self.format_amount(
                    line.get(
                        "debit",
                        "0.00",
                    )
                ),
                self.format_amount(
                    line.get(
                        "credit",
                        "0.00",
                    )
                ),
                line.get(
                    "description",
                    "",
                ),
            ]

            for column, value in enumerate(
                values
            ):
                item = QTableWidgetItem(
                    str(value)
                )

                if column in {
                    0,
                    1,
                }:
                    item.setTextAlignment(
                        Qt.AlignCenter
                    )

                if column in {
                    3,
                    4,
                }:
                    item.setTextAlignment(
                        Qt.AlignRight
                        | Qt.AlignVCenter
                    )

                self.voucher_table.setItem(
                    row,
                    column,
                    item,
                )

    def show_legal_basis(
        self,
        decision: dict,
    ):
        legal_basis = decision.get(
            "legal_basis",
            [],
        )

        if isinstance(legal_basis, str):
            legal_basis = [
                legal_basis
            ] if legal_basis.strip() else []

        if legal_basis:
            text = "\n\n".join(
                f"• {item}"
                for item in legal_basis
            )
        else:
            text = (
                "Bu kayıt için doğrulanmış ve "
                "sürümlenmiş mevzuat dayanağı "
                "henüz eklenmedi.\n\n"
                "Mevzuat doğrulaması tamamlanmadan "
                "otomatik aktarım yapılmamalıdır."
            )

        self.legal_basis_label.setText(text)

    def show_validation_result(
        self,
        validation_result: dict,
        decision: dict,
    ):
        errors = self.get_visible_validation_errors()

        warnings = list(
            validation_result.get(
                "warnings",
                [],
            )
        )

        decision_warnings = decision.get(
            "warnings",
            [],
        )

        for warning in decision_warnings:
            if warning not in warnings:
                warnings.append(warning)

        lines = []

        if errors:
            lines.append("Hatalar:")

            for error in errors:
                lines.append(
                    f"• {error}"
                )

        if warnings:
            if lines:
                lines.append("")

            lines.append("Uyarılar:")

            for warning in warnings:
                lines.append(
                    f"• {warning}"
                )

        if not errors and not warnings:
            lines.append(
                "✓ Temel muhasebe ve teknik "
                "kontroller başarılı."
            )

        self.findings_label.setText(
            "\n".join(lines)
        )

        if errors:
            self.findings_label.setStyleSheet("""
                background: #FFF1F1;
                color: #9F2424;
                border: 1px solid #F1B7B7;
                border-radius: 7px;
                padding: 10px;
                font-size: 11px;
            """)
        elif warnings:
            self.findings_label.setStyleSheet("""
                background: #FFF9EB;
                color: #805D13;
                border: 1px solid #F2D995;
                border-radius: 7px;
                padding: 10px;
                font-size: 11px;
            """)
        else:
            self.findings_label.setStyleSheet("""
                background: #EFFAF3;
                color: #187247;
                border: 1px solid #BEE4CE;
                border-radius: 7px;
                padding: 10px;
                font-size: 11px;
            """)

    def get_visible_validation_errors(
        self,
    ) -> list[str]:
        errors = self.validation_result.get(
            "errors",
            [],
        )

        return [
            error
            for error in errors
            if "Mali müşavir onayı"
            not in str(error)
        ]

    def load_pdf_from_document(
        self,
        document: dict,
    ):
        source_path = document.get(
            "source_file_path",
            "",
        )

        if not source_path:
            source_path = document.get(
                "source_file",
                "",
            )

        if (
            not source_path
            or not Path(source_path).exists()
        ):
            self.close_pdf_document()

            self.pdf_information_label.setText(
                "PDF dosya yolu fişe aktarılmadı."
            )
            self.pdf_preview_label.setText(
                "PDF önizlemesi bir sonraki "
                "bağlantı adımından sonra görünecek."
            )
            self.open_pdf_button.setEnabled(False)
            return

        try:
            self.close_pdf_document()

            self.pdf_path = str(source_path)
            self.pdf_document = pymupdf.open(
                self.pdf_path
            )
            self.current_pdf_page = 0

            self.pdf_information_label.setText(
                Path(self.pdf_path).name
            )
            self.open_pdf_button.setEnabled(True)

            self.render_current_pdf_page()

        except Exception as error:
            self.close_pdf_document()

            self.pdf_preview_label.setText(
                "PDF görüntülenemedi:\n\n"
                f"{error}"
            )

    def render_current_pdf_page(self):
        if not self.pdf_document:
            return

        page_count = (
            self.pdf_document.page_count
        )

        if page_count == 0:
            return

        self.current_pdf_page = max(
            0,
            min(
                self.current_pdf_page,
                page_count - 1,
            ),
        )

        page = self.pdf_document.load_page(
            self.current_pdf_page
        )

        pixmap = page.get_pixmap(
            matrix=pymupdf.Matrix(
                1.7,
                1.7,
            ),
            alpha=False,
        )

        image = QImage(
            pixmap.samples,
            pixmap.width,
            pixmap.height,
            pixmap.stride,
            QImage.Format.Format_RGB888,
        ).copy()

        self.current_pdf_pixmap = (
            QPixmap.fromImage(image)
        )

        self.refresh_pdf_preview_size()

        self.pdf_page_label.setText(
            f"Sayfa {self.current_pdf_page + 1} "
            f"/ {page_count}"
        )

        self.previous_page_button.setEnabled(
            self.current_pdf_page > 0
        )
        self.next_page_button.setEnabled(
            self.current_pdf_page
            < page_count - 1
        )

    def refresh_pdf_preview_size(self):
        if not self.current_pdf_pixmap:
            return

        available_width = max(
            240,
            self.pdf_scroll.viewport().width()
            - 22,
        )

        scaled_pixmap = (
            self.current_pdf_pixmap.scaledToWidth(
                available_width,
                Qt.SmoothTransformation,
            )
        )

        self.pdf_preview_label.setPixmap(
            scaled_pixmap
        )
        self.pdf_preview_label.resize(
            scaled_pixmap.size()
        )

    def show_previous_pdf_page(self):
        if (
            self.pdf_document
            and self.current_pdf_page > 0
        ):
            self.current_pdf_page -= 1
            self.render_current_pdf_page()

    def show_next_pdf_page(self):
        if (
            self.pdf_document
            and self.current_pdf_page
            < self.pdf_document.page_count - 1
        ):
            self.current_pdf_page += 1
            self.render_current_pdf_page()

    def open_pdf_external(self):
        if (
            self.pdf_path
            and Path(self.pdf_path).exists()
        ):
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(
                    self.pdf_path
                )
            )

    def toggle_voucher_focus(self):
        """
        Muhasebe fişini tek başına geniş ekranda gösterir.
        """

        if not self.focus_mode_enabled:
            self.normal_splitter_sizes = (
                self.main_splitter.sizes()
            )

            self.main_splitter.setSizes([
                0,
                max(
                    900,
                    self.width(),
                ),
                0,
            ])

            self.focus_button.setText(
                "◫ Tüm Paneller"
            )
            self.focus_mode_enabled = True

        else:
            self.main_splitter.setSizes(
                self.normal_splitter_sizes
            )

            self.focus_button.setText(
                "⛶ Fişi Genişlet"
            )
            self.focus_mode_enabled = False

    def approve_voucher(self):
        if not self.voucher_data:
            QMessageBox.warning(
                self,
                "Fiş Bulunamadı",
                "Onaylanacak muhasebe fişi bulunmuyor.",
            )
            return

        confirmation = QMessageBox.question(
            self,
            "Fiş Onayı",
            (
                "Muhasebe fişini kontrol ettiğinizi "
                "ve onayladığınızı kabul ediyor musunuz?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if confirmation != QMessageBox.Yes:
            return

        try:
            self.voucher_data = (
                self.voucher_engine.approve_voucher(
                    voucher_data=self.voucher_data,
                    approved_by="Ali Osman Hökelek",
                )
            )

            self.set_approved_state()

            self.voucher_approved.emit(
                self.voucher_data
            )

            QMessageBox.information(
                self,
                "Fiş Onaylandı",
                (
                    "Muhasebe fişi onaylandı.\n\n"
                    "Fiş ERP aktarımına hazırlanabilir."
                ),
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Onay Hatası",
                "Fiş onaylanamadı:\n\n"
                f"{error}",
            )

    def set_approved_state(self):
        self.header_status_label.setText(
            "✓ Onaylandı"
        )
        self.header_status_label.setStyleSheet("""
            background: #EAF8EF;
            color: #138A4B;
            border-radius: 17px;
            padding: 0 16px;
            font-size: 11px;
            font-weight: 700;
        """)

        self.status_label.setText(
            "Durum: Fiş onaylandı"
        )
        self.status_label.setStyleSheet("""
            color: #159A55;
            font-size: 12px;
            font-weight: 800;
            border: none;
        """)

        self.approve_button.setText(
            "✓ Onaylandı"
        )
        self.approve_button.setEnabled(False)

    def show_reanalysis_information(self):
        QMessageBox.information(
            self,
            "Analizi Yenile",
            (
                "Yeni analiz için PDF Faturalar "
                "ekranından belgeyi yeniden seçebilirsiniz."
            ),
        )

    def format_amount(
        self,
        value,
    ) -> str:
        try:
            normalized = str(value).strip()

            if "," in normalized:
                normalized = (
                    normalized
                    .replace(".", "")
                    .replace(",", ".")
                )

            amount = float(normalized)

            return (
                f"{amount:,.2f}"
                .replace(",", "_")
                .replace(".", ",")
                .replace("_", ".")
            )

        except (
            TypeError,
            ValueError,
        ):
            return str(value)

    def close_pdf_document(self):
        if self.pdf_document is not None:
            try:
                self.pdf_document.close()
            except Exception:
                pass

        self.pdf_document = None
        self.pdf_path = None
        self.current_pdf_pixmap = None
        self.current_pdf_page = 0

        self.pdf_page_label.setText(
            "Sayfa - / -"
        )
        self.previous_page_button.setEnabled(
            False
        )
        self.next_page_button.setEnabled(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_pdf_preview_size()

    def create_card(self) -> QFrame:
        frame = QFrame()
        frame.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )
        frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #DCE4EE;
                border-radius: 10px;
            }
        """)

        return frame

    def create_information_card(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E1E7EF;
                border-radius: 9px;
            }
        """)

        return frame

    def section_title_style(self) -> str:
        return """
            color: #172033;
            font-size: 14px;
            font-weight: 800;
            border: none;
        """

    def secondary_button_style(self) -> str:
        return """
            QPushButton {
                background: white;
                color: #31577F;
                border: 1px solid #BFCBDA;
                border-radius: 7px;
                padding: 0 11px;
                font-size: 11px;
                font-weight: 700;
            }

            QPushButton:hover {
                background: #F1F6FE;
                border-color: #7FA7D3;
            }

            QPushButton:disabled {
                background: #F1F5F9;
                color: #A0AEC0;
                border-color: #E2E8F0;
            }
        """
