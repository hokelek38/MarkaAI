import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from services.company_profile_service import CompanyProfileService


class CompanyDialog(QDialog):
    """
    Yeni firma kayıt penceresi.

    Kaydedilen firma:
    - Firma listesinde gösterilir
    - VKN/TCKN üzerinden tanınır
    - Faaliyet türüne göre muhasebe kararlarında kullanılır
    """

    ACTIVITY_TYPES = {
        "manufacturing": "Üretim",
        "trading": "Ticaret / Al-Sat",
        "service": "Hizmet",
        "export": "İhracat",
        "import": "İthalat",
    }

    def __init__(
        self,
        parent=None,
        company_service=None,
    ):
        super().__init__(parent)

        self.company_service = (
            company_service
            or CompanyProfileService()
        )

        self.created_company = None
        self.activity_checkboxes = {}

        self.setWindowTitle("Yeni Firma Ekle")
        self.setMinimumWidth(620)
        self.setModal(True)

        self.build_ui()

    def build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(18)

        title = QLabel("Yeni Firma Tanımlama")
        title.setStyleSheet("""
            font-size: 22px;
            font-weight: bold;
            color: #1F2937;
        """)

        description = QLabel(
            "Firma bilgilerini bir kez kaydedin. "
            "MarkaAI sonraki faturalarda firmayı VKN/TCKN "
            "üzerinden otomatik tanıyacaktır."
        )
        description.setWordWrap(True)
        description.setStyleSheet("""
            font-size: 13px;
            color: #64748B;
        """)

        main_layout.addWidget(title)
        main_layout.addWidget(description)

        form_frame = QFrame()
        form_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
        """)

        form_layout = QFormLayout(form_frame)
        form_layout.setContentsMargins(22, 22, 22, 22)
        form_layout.setHorizontalSpacing(20)
        form_layout.setVerticalSpacing(14)
        form_layout.setLabelAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )

        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText(
            "Örnek: Piyano Genç Odası Mobilya Ltd. Şti."
        )

        self.tax_number_input = QLineEdit()
        self.tax_number_input.setPlaceholderText(
            "10 haneli VKN veya 11 haneli TCKN"
        )
        self.tax_number_input.setMaxLength(11)

        self.sector_input = QLineEdit()
        self.sector_input.setPlaceholderText(
            "Örnek: Mobilya, inşaat, tekstil, danışmanlık"
        )

        self.activity_description_input = QLineEdit()
        self.activity_description_input.setPlaceholderText(
            "Firmanın yaptığı işi kısaca açıklayın"
        )

        self.nace_input = QLineEdit()
        self.nace_input.setPlaceholderText(
            "Birden fazla kodu virgülle ayırabilirsiniz"
        )

        self.erp_selector = QComboBox()
        self.erp_selector.addItem(
            "Henüz seçilmedi",
            "",
        )
        self.erp_selector.addItem(
            "Luca",
            "luca",
        )
        self.erp_selector.addItem(
            "Zirve",
            "zirve",
        )
        self.erp_selector.addItem(
            "Logo",
            "logo",
        )
        self.erp_selector.addItem(
            "Mikro",
            "mikro",
        )
        self.erp_selector.addItem(
            "Netsis",
            "netsis",
        )
        self.erp_selector.addItem(
            "Diğer",
            "other",
        )

        input_widgets = [
            self.title_input,
            self.tax_number_input,
            self.sector_input,
            self.activity_description_input,
            self.nace_input,
            self.erp_selector,
        ]

        for widget in input_widgets:
            widget.setMinimumHeight(40)
            widget.setStyleSheet("""
                QLineEdit,
                QComboBox {
                    background: #F8FAFC;
                    color: #1F2937;
                    border: 1px solid #CBD5E1;
                    border-radius: 8px;
                    padding: 7px 10px;
                    font-size: 13px;
                }

                QLineEdit:focus,
                QComboBox:focus {
                    border-color: #2563EB;
                }
            """)

        form_layout.addRow(
            self.create_required_label("Firma Unvanı"),
            self.title_input,
        )
        form_layout.addRow(
            self.create_required_label("VKN / TCKN"),
            self.tax_number_input,
        )
        form_layout.addRow(
            QLabel("Sektör"),
            self.sector_input,
        )
        form_layout.addRow(
            QLabel("Faaliyet Açıklaması"),
            self.activity_description_input,
        )

        activity_widget = QFrame()
        activity_widget.setStyleSheet("""
            QFrame {
                background: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
        """)

        activity_layout = QVBoxLayout(
            activity_widget
        )
        activity_layout.setContentsMargins(
            12,
            10,
            12,
            10,
        )
        activity_layout.setSpacing(8)

        activity_row_one = QHBoxLayout()
        activity_row_two = QHBoxLayout()

        for index, (
            activity_code,
            activity_name,
        ) in enumerate(
            self.ACTIVITY_TYPES.items()
        ):
            checkbox = QCheckBox(activity_name)
            checkbox.stateChanged.connect(
                self.refresh_primary_activities
            )
            checkbox.setStyleSheet("""
                QCheckBox {
                    color: #334155;
                    font-size: 13px;
                    spacing: 7px;
                }
            """)

            self.activity_checkboxes[
                activity_code
            ] = checkbox

            if index < 3:
                activity_row_one.addWidget(
                    checkbox
                )
            else:
                activity_row_two.addWidget(
                    checkbox
                )

        activity_row_one.addStretch()
        activity_row_two.addStretch()

        activity_layout.addLayout(
            activity_row_one
        )
        activity_layout.addLayout(
            activity_row_two
        )

        form_layout.addRow(
            self.create_required_label(
                "Faaliyet Türleri"
            ),
            activity_widget,
        )

        self.primary_activity_selector = QComboBox()
        self.primary_activity_selector.setMinimumHeight(
            40
        )
        self.primary_activity_selector.setEnabled(
            False
        )
        self.primary_activity_selector.setStyleSheet("""
            QComboBox {
                background: #F8FAFC;
                color: #1F2937;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                padding: 7px 10px;
                font-size: 13px;
            }

            QComboBox:disabled {
                background: #F1F5F9;
                color: #94A3B8;
            }
        """)

        form_layout.addRow(
            self.create_required_label(
                "Ana Faaliyet"
            ),
            self.primary_activity_selector,
        )

        form_layout.addRow(
            QLabel("NACE Kodları"),
            self.nace_input,
        )
        form_layout.addRow(
            QLabel("Muhasebe Programı"),
            self.erp_selector,
        )

        main_layout.addWidget(form_frame)

        information_label = QLabel(
            "Bir firma aynı anda üretim, ticaret ve hizmet "
            "faaliyetlerine sahip olabilir. Ana faaliyet, "
            "varsayılan muhasebe değerlendirmelerinde kullanılır."
        )
        information_label.setWordWrap(True)
        information_label.setStyleSheet("""
            background: #EFF6FF;
            color: #1E40AF;
            border: 1px solid #BFDBFE;
            border-radius: 8px;
            padding: 10px;
            font-size: 12px;
        """)

        main_layout.addWidget(information_label)

        buttons = QDialogButtonBox()

        self.cancel_button = QPushButton(
            "İptal"
        )
        self.save_button = QPushButton(
            "Firmayı Kaydet"
        )

        self.cancel_button.setMinimumHeight(42)
        self.save_button.setMinimumHeight(42)

        self.cancel_button.clicked.connect(
            self.reject
        )
        self.save_button.clicked.connect(
            self.save_company
        )

        self.cancel_button.setStyleSheet("""
            QPushButton {
                background: white;
                color: #475569;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #F8FAFC;
            }
        """)

        self.save_button.setStyleSheet("""
            QPushButton {
                background: #2563EB;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 20px;
                font-size: 13px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #1D4ED8;
            }

            QPushButton:pressed {
                background: #1E40AF;
            }
        """)

        buttons.addButton(
            self.cancel_button,
            QDialogButtonBox.RejectRole,
        )
        buttons.addButton(
            self.save_button,
            QDialogButtonBox.AcceptRole,
        )

        main_layout.addWidget(buttons)

    def create_required_label(
        self,
        text: str,
    ) -> QLabel:
        label = QLabel(
            f"{text} <span style='color:#DC2626;'>*</span>"
        )
        label.setTextFormat(Qt.RichText)

        return label

    def get_selected_activity_types(
        self,
    ) -> list[str]:
        selected = []

        for activity_code, checkbox in (
            self.activity_checkboxes.items()
        ):
            if checkbox.isChecked():
                selected.append(activity_code)

        return selected

    def refresh_primary_activities(self):
        current_activity = (
            self.primary_activity_selector.currentData()
        )

        selected_activities = (
            self.get_selected_activity_types()
        )

        self.primary_activity_selector.blockSignals(
            True
        )
        self.primary_activity_selector.clear()

        for activity_code in selected_activities:
            self.primary_activity_selector.addItem(
                self.ACTIVITY_TYPES[
                    activity_code
                ],
                activity_code,
            )

        self.primary_activity_selector.setEnabled(
            bool(selected_activities)
        )

        if (
            current_activity
            in selected_activities
        ):
            current_index = (
                self.primary_activity_selector.findData(
                    current_activity
                )
            )

            self.primary_activity_selector.setCurrentIndex(
                current_index
            )

        self.primary_activity_selector.blockSignals(
            False
        )

    def save_company(self):
        title = self.title_input.text().strip()

        tax_number = re.sub(
            r"\D",
            "",
            self.tax_number_input.text(),
        )

        activity_types = (
            self.get_selected_activity_types()
        )

        primary_activity_type = (
            self.primary_activity_selector.currentData()
        )

        if not title:
            QMessageBox.warning(
                self,
                "Eksik Bilgi",
                "Firma unvanını girin.",
            )
            self.title_input.setFocus()
            return

        if len(tax_number) not in {10, 11}:
            QMessageBox.warning(
                self,
                "Geçersiz Vergi Numarası",
                "VKN 10, TCKN 11 haneli olmalıdır.",
            )
            self.tax_number_input.setFocus()
            return

        if not activity_types:
            QMessageBox.warning(
                self,
                "Faaliyet Türü Seçilmedi",
                "En az bir faaliyet türü seçin.",
            )
            return

        if not primary_activity_type:
            QMessageBox.warning(
                self,
                "Ana Faaliyet Seçilmedi",
                "Firmanın ana faaliyet türünü seçin.",
            )
            return

        nace_codes = [
            code.strip()
            for code in self.nace_input.text().split(",")
            if code.strip()
        ]

        company_data = {
            "title": title,
            "tax_number": tax_number,
            "activity_types": activity_types,
            "primary_activity_type": (
                primary_activity_type
            ),
            "sector": self.sector_input.text().strip(),
            "activity_description": (
                self.activity_description_input
                .text()
                .strip()
            ),
            "nace_codes": nace_codes,
            "erp_system": (
                self.erp_selector.currentData()
            ),
            "active": True,
            "license_active": True,
        }

        try:
            self.created_company = (
                self.company_service.add_company(
                    company_data
                )
            )

            QMessageBox.information(
                self,
                "Firma Kaydedildi",
                (
                    f"{title} başarıyla kaydedildi.\n\n"
                    "Firma artık yan menüde görünecek ve "
                    "faturaları VKN/TCKN üzerinden tanınacaktır."
                ),
            )

            self.accept()

        except Exception as error:
            QMessageBox.critical(
                self,
                "Firma Kayıt Hatası",
                f"Firma kaydedilemedi:\n\n{error}",
            )

    def get_created_company(
        self,
    ) -> dict | None:
        return self.created_company