from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.company_profile_service import CompanyProfileService
from services.decision.decision_engine import DecisionEngine
from services.pdf_service import PdfService
from ui.theme import Theme


class PdfPage(QWidget):
    """
    Tek veya birden fazla fatura içeren PDF dosyalarını okur.

    Kullanıcı PDF içindeki faturalar arasında seçim yapabilir.
    Seçilen fatura DecisionEngine ile muhasebeleştirilir.
    """

    analysis_ready = Signal(object, object)
    analysis_review_required = Signal(object, object, object)

    def __init__(self):
        super().__init__()

        self.selected_file = None
        self.invoices = []
        self.invoice_data = None

        self.pdf_service = PdfService()
        self.decision_engine = DecisionEngine()
        self.company_profile_service = CompanyProfileService()

        # Firma seçme ekranı eklenene kadar geliştirme firması.
        self.company_id = "demo_manufacturing"

        # Firma VKN/TCKN bilgisi taraflarla eşleşmezse
        # belge alış faturası kabul edilir.
        self.default_document_direction = "purchase"

        self.build_ui()

    def build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(16)

        title = QLabel("PDF Fatura Aktar")
        title.setStyleSheet(f"""
            font-size: {Theme.TITLE}px;
            font-weight: bold;
            color: {Theme.TEXT};
        """)

        subtitle = QLabel(
            "Tek veya birden fazla fatura içeren PDF dosyasını seçin. "
            "MarkaAI faturaları ayırıp muhasebe fişi önerisi oluştursun."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"""
            font-size: {Theme.NORMAL}px;
            color: {Theme.SUBTEXT};
        """)

        # PDF yükleme alanı
        upload_frame = QFrame()
        upload_frame.setMinimumHeight(185)
        upload_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 2px dashed #CBD5E1;
                border-radius: 14px;
            }
        """)

        upload_layout = QVBoxLayout(upload_frame)
        upload_layout.setContentsMargins(25, 20, 25, 20)
        upload_layout.setSpacing(10)
        upload_layout.setAlignment(Qt.AlignCenter)

        upload_icon = QLabel("📄")
        upload_icon.setAlignment(Qt.AlignCenter)
        upload_icon.setStyleSheet("""
            font-size: 42px;
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
            "Birleşik PDF içindeki farklı faturalar otomatik ayrılacaktır."
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
        select_button.setMinimumHeight(44)
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

        upload_layout.addWidget(upload_icon)
        upload_layout.addWidget(upload_title)
        upload_layout.addWidget(upload_description)
        upload_layout.addWidget(
            select_button,
            alignment=Qt.AlignCenter,
        )

        # Fatura seçim alanı
        selection_frame = QFrame()
        selection_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
        """)

        selection_layout = QHBoxLayout(selection_frame)
        selection_layout.setContentsMargins(20, 14, 20, 14)
        selection_layout.setSpacing(16)

        selection_text_layout = QVBoxLayout()
        selection_text_layout.setSpacing(4)

        selection_title = QLabel("PDF İçindeki Faturalar")
        selection_title.setStyleSheet("""
            font-size: 15px;
            font-weight: bold;
            color: #1F2937;
            border: none;
        """)

        self.invoice_count_label = QLabel(
            "Henüz PDF seçilmedi."
        )
        self.invoice_count_label.setStyleSheet("""
            font-size: 13px;
            color: #64748B;
            border: none;
        """)

        selection_text_layout.addWidget(selection_title)
        selection_text_layout.addWidget(
            self.invoice_count_label
        )

        self.invoice_selector = QComboBox()
        self.invoice_selector.setMinimumWidth(500)
        self.invoice_selector.setMinimumHeight(42)
        self.invoice_selector.setEnabled(False)
        self.invoice_selector.currentIndexChanged.connect(
            self.change_selected_invoice
        )
        self.invoice_selector.setStyleSheet("""
            QComboBox {
                background: #F8FAFC;
                color: #334155;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
            }

            QComboBox:hover {
                border-color: #2563EB;
            }

            QComboBox:disabled {
                background: #F1F5F9;
                color: #94A3B8;
            }

            QComboBox QAbstractItemView {
                background: white;
                color: #334155;
                border: 1px solid #CBD5E1;
                selection-background-color: #DBEAFE;
                selection-color: #1E3A8A;
            }
        """)

        selection_layout.addLayout(selection_text_layout)
        selection_layout.addStretch()
        selection_layout.addWidget(self.invoice_selector)

        # Fatura bilgi alanı
        information_frame = QFrame()
        information_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
        """)

        information_layout = QVBoxLayout(information_frame)
        information_layout.setContentsMargins(24, 18, 24, 18)
        information_layout.setSpacing(9)

        information_title = QLabel("Seçilen Fatura Bilgileri")
        information_title.setStyleSheet("""
            font-size: 17px;
            font-weight: bold;
            color: #1F2937;
            border: none;
        """)

        self.file_label = QLabel("Dosya: Henüz PDF seçilmedi")
        self.page_count_label = QLabel("PDF Toplam Sayfa Sayısı: -")
        self.page_range_label = QLabel("Faturanın Bulunduğu Sayfa: -")
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
            self.page_range_label,
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

        information_layout.addWidget(information_title)

        for label in information_labels:
            label.setWordWrap(True)
            label.setStyleSheet("""
                font-size: 13px;
                color: #475569;
                border: none;
                padding: 1px;
            """)
            information_layout.addWidget(label)

        # Analiz butonu
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.analyze_button = QPushButton(
            "🤖 Seçilen Faturayı Analiz Et"
        )
        self.analyze_button.setMinimumHeight(48)
        self.analyze_button.setFixedWidth(270)
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
        main_layout.addWidget(selection_frame)
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

        self.reset_pdf_state()

        self.selected_file = file_path
        self.file_label.setText(
            f"Dosya: {Path(file_path).name}"
        )

        try:
            self.invoices = self.pdf_service.analyze_invoices(
                file_path
            )

            for invoice in self.invoices:
                invoice["source_file_path"] = file_path

            if not self.invoices:
                raise ValueError(
                    "PDF içinde analiz edilebilecek fatura bulunamadı."
                )

            self.populate_invoice_selector()

            self.invoice_data = self.invoices[0]
            self.show_invoice_information(
                self.invoice_data
            )

            self.invoice_selector.setEnabled(True)
            self.analyze_button.setEnabled(True)

            invoice_count = len(self.invoices)

            if invoice_count == 1:
                message = (
                    "PDF başarıyla okundu.\n\n"
                    "1 fatura bulundu."
                )
            else:
                message = (
                    "PDF başarıyla okundu.\n\n"
                    f"{invoice_count} farklı fatura bulundu.\n"
                    "Analiz edilecek faturayı listeden seçebilirsiniz."
                )

            QMessageBox.information(
                self,
                "PDF Analizi Tamamlandı",
                message,
            )

        except Exception as error:
            self.reset_pdf_state()

            QMessageBox.critical(
                self,
                "PDF Okuma Hatası",
                f"PDF okunurken bir hata oluştu:\n\n{error}",
            )

    def populate_invoice_selector(self):
        """
        PDF içindeki faturaları seçim kutusuna ekler.
        """

        self.invoice_selector.blockSignals(True)
        self.invoice_selector.clear()

        invoice_count = len(self.invoices)

        self.invoice_count_label.setText(
            f"Dosyada {invoice_count} fatura bulundu."
        )

        for invoice in self.invoices:
            invoice_index = invoice.get(
                "invoice_index",
                "-",
            )
            invoice_number = invoice.get(
                "invoice_number",
                "-",
            )
            seller_name = invoice.get(
                "seller_name",
                "-",
            )
            total_amount = invoice.get(
                "total_amount",
                "-",
            )
            page_range = invoice.get(
                "page_range",
                "-",
            )

            item_text = (
                f"{invoice_index}. "
                f"{invoice_number} | "
                f"{seller_name} | "
                f"{total_amount} | "
                f"Sayfa {page_range}"
            )

            self.invoice_selector.addItem(
                item_text
            )

        self.invoice_selector.setCurrentIndex(0)
        self.invoice_selector.blockSignals(False)

    def change_selected_invoice(
        self,
        index: int,
    ):
        """
        Kullanıcı farklı bir fatura seçtiğinde
        ekrandaki bilgileri günceller.
        """

        if index < 0 or index >= len(self.invoices):
            self.invoice_data = None
            self.analyze_button.setEnabled(False)
            return

        self.invoice_data = self.invoices[index]

        self.show_invoice_information(
            self.invoice_data
        )

        self.analyze_button.setEnabled(True)

    def show_invoice_information(
        self,
        data: dict,
    ):
        self.file_label.setText(
            f"Dosya: {data.get('file_name', '-')}"
        )

        self.page_count_label.setText(
            "PDF Toplam Sayfa Sayısı: "
            f"{data.get('document_page_count', '-')}"
        )

        self.page_range_label.setText(
            "Faturanın Bulunduğu Sayfa: "
            f"{data.get('page_range', '-')}"
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
            "Satıcı VKN / TCKN: "
            f"{data.get('seller_tax_number', '-')}"
        )

        self.buyer_label.setText(
            f"Alıcı: {data.get('buyer_name', '-')}"
        )

        self.subtotal_label.setText(
            "Mal Hizmet Toplamı: "
            f"{data.get('subtotal', '-')}"
        )

        self.vat_label.setText(
            "Hesaplanan KDV: "
            f"{data.get('vat_amount', '-')}"
        )

        self.total_label.setText(
            "Genel Toplam: "
            f"{data.get('total_amount', '-')}"
        )

        self.payable_label.setText(
            "Ödenecek Tutar: "
            f"{data.get('payable_amount', '-')}"
        )

    def reset_pdf_state(self):
        """
        Önceki PDF ve fatura bilgilerini temizler.
        """

        self.selected_file = None
        self.invoices = []
        self.invoice_data = None

        self.invoice_selector.blockSignals(True)
        self.invoice_selector.clear()
        self.invoice_selector.blockSignals(False)
        self.invoice_selector.setEnabled(False)

        self.invoice_count_label.setText(
            "Henüz PDF seçilmedi."
        )

        self.file_label.setText(
            "Dosya: Henüz PDF seçilmedi"
        )
        self.page_count_label.setText(
            "PDF Toplam Sayfa Sayısı: -"
        )
        self.page_range_label.setText(
            "Faturanın Bulunduğu Sayfa: -"
        )
        self.invoice_number_label.setText(
            "Fatura No: -"
        )
        self.date_label.setText(
            "Fatura Tarihi: -"
        )
        self.company_label.setText(
            "Satıcı: -"
        )
        self.tax_number_label.setText(
            "Satıcı VKN / TCKN: -"
        )
        self.buyer_label.setText(
            "Alıcı: -"
        )
        self.subtotal_label.setText(
            "Mal Hizmet Toplamı: -"
        )
        self.vat_label.setText(
            "Hesaplanan KDV: -"
        )
        self.total_label.setText(
            "Genel Toplam: -"
        )
        self.payable_label.setText(
            "Ödenecek Tutar: -"
        )

        self.analyze_button.setEnabled(False)
        self.analyze_button.setText(
            "🤖 Seçilen Faturayı Analiz Et"
        )

    def analyze_pdf(self):
        """
        Listeden seçilen faturayı DecisionEngine ile analiz eder.
        """

        if not self.selected_file or not self.invoice_data:
            QMessageBox.warning(
                self,
                "Fatura Seçilmedi",
                "Lütfen önce bir PDF ve fatura seçin.",
            )
            return

        self.analyze_button.setEnabled(False)
        self.analyze_button.setText(
            "Analiz ediliyor..."
        )

        try:
            company = (
                self.company_profile_service.get_company_by_id(
                    self.company_id
                )
            )

            if not company:
                raise ValueError(
                    "Aktif firma profili bulunamadı: "
                    f"{self.company_id}"
                )

            document_direction = (
                self._detect_document_direction(
                    company
                )
            )

            result = self.decision_engine.process_invoice(
                invoice_data=self.invoice_data,
                company=company,
                company_id=self.company_id,
                document_direction=document_direction,
                context={},
            )

            if not result.get("success"):
                line_usage_review = (
                    result.get(
                        "line_usage_review",
                        {},
                    )
                    or {}
                )

                unresolved_lines = list(
                    line_usage_review.get(
                        "unresolved_lines",
                        [],
                    )
                )

                if (
                    line_usage_review.get(
                        "blocked",
                        False,
                    )
                    and unresolved_lines
                ):
                    self.analysis_review_required.emit(
                        result,
                        dict(self.invoice_data),
                        dict(company),
                    )
                    return

                errors = result.get(
                    "errors",
                    [
                        "Muhasebe analizi oluşturulamadı."
                    ],
                )

                raise ValueError(
                    "\n".join(errors)
                )

            voucher_data = result.get("voucher")
            validation_result = (
                result.get("validation") or {}
            )

            if not voucher_data:
                raise ValueError(
                    "DecisionEngine geçerli bir MSV fişi üretmedi."
                )

            self.analysis_ready.emit(
                voucher_data,
                validation_result,
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Muhasebe Analizi Hatası",
                "Muhasebe fişi oluşturulurken "
                "bir hata oluştu:\n\n"
                f"{error}",
            )

        finally:
            self.analyze_button.setText(
                "🤖 Seçilen Faturayı Analiz Et"
            )
            self.analyze_button.setEnabled(
                self.invoice_data is not None
            )

    def apply_line_usage_review(
        self,
        payload: dict,
    ) -> None:
        """
        Seçilen kullanım amaçlarını fatura
        kalemlerine uygular ve yeniden analiz eder.
        """

        try:
            if not isinstance(payload, dict):
                raise ValueError(
                    "Kullanım amacı seçim verisi geçersiz."
                )

            invoice_data = deepcopy(
                payload.get(
                    "invoice_data",
                    {},
                )
            )

            company = deepcopy(
                payload.get(
                    "company",
                    {},
                )
            )

            selections = list(
                payload.get(
                    "selections",
                    [],
                )
            )

            line_items = [
                dict(line_item)
                for line_item in invoice_data.get(
                    "line_items",
                    [],
                )
                if isinstance(line_item, dict)
            ]

            if not selections:
                raise ValueError(
                    "Uygulanacak kullanım amacı "
                    "seçimi bulunamadı."
                )

            if not line_items:
                raise ValueError(
                    "Faturada güncellenecek "
                    "kalem bulunamadı."
                )

            matched_indexes = set()

            for selection in selections:
                usage_code = str(
                    selection.get(
                        "usage",
                        "",
                    )
                ).strip()

                if not usage_code:
                    raise ValueError(
                        "Kullanım amacı boş bırakılamaz."
                    )

                if usage_code == "fixed_asset":
                    QMessageBox.information(
                        self,
                        "Duran Varlık Hesabı",
                        (
                            "Duran varlık için 252, 253, "
                            "254 veya 255 hesaplarından "
                            "uygun olanı ayrıca seçilmelidir."
                            "\n\n"
                            "Duran varlık hesap seçim "
                            "ekranını sonraki aşamada "
                            "ekleyeceğiz."
                        ),
                    )
                    return

                line_number = selection.get(
                    "line_number",
                    "",
                )

                description = str(
                    selection.get(
                        "description",
                        "",
                    )
                ).strip()

                selected_index = None

                # Önce satır numarasıyla eşleştir.
                if line_number not in {
                    None,
                    "",
                }:
                    for index, line_item in enumerate(
                        line_items
                    ):
                        if index in matched_indexes:
                            continue

                        current_line_number = (
                            line_item.get(
                                "line_number",
                                "",
                            )
                        )

                        if (
                            str(current_line_number)
                            == str(line_number)
                        ):
                            selected_index = index
                            break

                # Satır numarası bulunmazsa
                # açıklamayla eşleştir.
                if selected_index is None:
                    for index, line_item in enumerate(
                        line_items
                    ):
                        if index in matched_indexes:
                            continue

                        current_description = str(
                            line_item.get(
                                "description",
                                "",
                            )
                        ).strip()

                        if (
                            current_description
                            == description
                        ):
                            selected_index = index
                            break

                if selected_index is None:
                    raise ValueError(
                        (
                            "Kullanım amacı seçilen "
                            "fatura kalemi asıl faturada "
                            "bulunamadı:\n"
                            f"{description or line_number}"
                        )
                    )

                line_items[selected_index][
                    "user_selected_usage"
                ] = usage_code

                line_items[selected_index][
                    "usage_confirmation_source"
                ] = "accounting_page"

                line_items[selected_index][
                    "usage_confirmed_by_user"
                ] = True

                matched_indexes.add(
                    selected_index
                )

            invoice_data["line_items"] = (
                line_items
            )

            self.invoice_data = invoice_data

            company_id = str(
                company.get(
                    "company_id",
                    self.company_id,
                )
                or self.company_id
            )

            document_direction = (
                self._detect_document_direction(
                    company
                )
            )

            result = (
                self.decision_engine.process_invoice(
                    invoice_data=invoice_data,
                    company=company,
                    company_id=company_id,
                    document_direction=(
                        document_direction
                    ),
                    context={},
                )
            )

            if result.get(
                "success",
                False,
            ):
                voucher_data = result.get(
                    "voucher"
                )

                validation_result = (
                    result.get(
                        "validation"
                    )
                    or {}
                )

                if not voucher_data:
                    raise ValueError(
                        "Yeniden analiz sonucunda "
                        "geçerli muhasebe fişi oluşmadı."
                    )

                self.analysis_ready.emit(
                    voucher_data,
                    validation_result,
                )
                return

            line_usage_review = (
                result.get(
                    "line_usage_review",
                    {},
                )
                or {}
            )

            unresolved_lines = list(
                line_usage_review.get(
                    "unresolved_lines",
                    [],
                )
            )

            if (
                line_usage_review.get(
                    "blocked",
                    False,
                )
                and unresolved_lines
            ):
                self.analysis_review_required.emit(
                    result,
                    invoice_data,
                    company,
                )
                return

            errors = list(
                result.get(
                    "errors",
                    [
                        "Yeniden muhasebe analizi "
                        "oluşturulamadı."
                    ],
                )
            )

            raise ValueError(
                "\n".join(
                    str(error)
                    for error in errors
                )
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Yeniden Analiz Hatası",
                (
                    "Kullanım amacı seçimleri "
                    "uygulanırken bir hata oluştu:"
                    "\n\n"
                    f"{error}"
                ),
            )

    def _detect_document_direction(
        self,
        company: dict,
    ) -> str:
        """
        Aktif firmanın belge üzerindeki tarafına göre
        alış veya satış yönünü belirler.
        """

        company_tax_number = str(
            company.get("tax_number", "")
        ).strip()

        seller_tax_number = str(
            self.invoice_data.get(
                "seller_tax_number",
                "",
            )
        ).strip()

        buyer_tax_number = str(
            self.invoice_data.get(
                "buyer_tax_number",
                "",
            )
        ).strip()

        if (
            company_tax_number
            and company_tax_number == seller_tax_number
        ):
            return "sale"

        if (
            company_tax_number
            and company_tax_number == buyer_tax_number
        ):
            return "purchase"

        return self.default_document_direction
