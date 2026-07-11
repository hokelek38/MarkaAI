from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class Dashboard(QWidget):
    """
    Seçili firmanın ana çalışma ekranı.

    İçerik:
    - Firma bilgileri
    - Faaliyet durumu
    - Varsayılan muhasebe bilgileri
    - Hızlı belge aktarım işlemleri
    """

    page_requested = Signal(str)

    ACTIVITY_NAMES = {
        "manufacturing": "İmalat",
        "trading": "Ticaret / Al-Sat",
        "service": "Hizmet",
        "export": "İhracat",
        "import": "İthalat",
    }

    ERP_NAMES = {
        "luca": "Luca",
        "zirve": "Zirve",
        "logo": "Logo",
        "mikro": "Mikro",
        "netsis": "Netsis",
        "other": "Diğer",
    }

    def __init__(self):
        super().__init__()

        self.active_company = None
        self.quick_action_buttons = []

        self.build_ui()
        self.clear_company_information()

    def build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        scroll_area.setStyleSheet("""
            QScrollArea {
                background: #F4F7FB;
                border: none;
            }

            QScrollBar:vertical {
                background: #F1F5F9;
                width: 9px;
            }

            QScrollBar::handle:vertical {
                background: #CBD5E1;
                border-radius: 4px;
                min-height: 35px;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        content_widget = QWidget()
        content_widget.setStyleSheet("""
            background: #F4F7FB;
        """)

        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 30)
        content_layout.setSpacing(18)

        # Sayfa başlığı
        header_layout = QHBoxLayout()

        header_text_layout = QVBoxLayout()
        header_text_layout.setSpacing(3)

        self.page_title = QLabel("Firma Paneli")
        self.page_title.setStyleSheet("""
            color: #172033;
            font-size: 25px;
            font-weight: 800;
        """)

        self.page_subtitle = QLabel(
            "Firma bilgileri ve hızlı muhasebe işlemleri"
        )
        self.page_subtitle.setStyleSheet("""
            color: #64748B;
            font-size: 13px;
        """)

        header_text_layout.addWidget(self.page_title)
        header_text_layout.addWidget(self.page_subtitle)

        self.active_company_badge = QLabel(
            "Firma seçilmedi"
        )
        self.active_company_badge.setAlignment(
            Qt.AlignCenter
        )
        self.active_company_badge.setMinimumHeight(34)
        self.active_company_badge.setStyleSheet("""
            background: #E2E8F0;
            color: #64748B;
            border-radius: 17px;
            padding: 0 15px;
            font-size: 12px;
            font-weight: 700;
        """)

        header_layout.addLayout(header_text_layout)
        header_layout.addStretch()
        header_layout.addWidget(
            self.active_company_badge
        )

        content_layout.addLayout(header_layout)

        # Üst bölüm
        top_grid = QGridLayout()
        top_grid.setHorizontalSpacing(16)
        top_grid.setVerticalSpacing(16)
        top_grid.setColumnStretch(0, 1)
        top_grid.setColumnStretch(1, 1)

        self.company_card = (
            self.create_company_information_card()
        )
        self.quick_actions_card = (
            self.create_quick_actions_card()
        )

        top_grid.addWidget(
            self.company_card,
            0,
            0,
        )
        top_grid.addWidget(
            self.quick_actions_card,
            0,
            1,
        )

        content_layout.addLayout(top_grid)

        # Alt bilgi kartı
        content_layout.addWidget(
            self.create_workflow_card()
        )

        content_layout.addStretch()

        scroll_area.setWidget(content_widget)
        root_layout.addWidget(scroll_area)

    def create_company_information_card(
        self,
    ) -> QFrame:
        frame = self.create_card()

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)

        header_layout = QHBoxLayout()

        icon = QLabel("▦")
        icon.setStyleSheet("""
            color: #1769D2;
            font-size: 21px;
            font-weight: bold;
        """)

        title = QLabel("Firma Bilgileri")
        title.setStyleSheet("""
            color: #172033;
            font-size: 16px;
            font-weight: 800;
        """)

        edit_button = QPushButton("✎  Düzenle")
        edit_button.setFixedHeight(34)
        edit_button.setCursor(
            Qt.PointingHandCursor
        )
        edit_button.clicked.connect(
            lambda: self.page_requested.emit(
                "Ayarlar"
            )
        )
        edit_button.setStyleSheet("""
            QPushButton {
                background: white;
                color: #334155;
                border: 1px solid #CBD5E1;
                border-radius: 7px;
                padding: 0 13px;
                font-size: 11px;
                font-weight: 700;
            }

            QPushButton:hover {
                background: #F8FAFC;
                border-color: #94A3B8;
            }
        """)

        header_layout.addWidget(icon)
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(edit_button)

        layout.addLayout(header_layout)

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet("""
            background: #E5EAF1;
            border: none;
        """)

        layout.addWidget(separator)

        information_grid = QGridLayout()
        information_grid.setHorizontalSpacing(24)
        information_grid.setVerticalSpacing(11)
        information_grid.setColumnStretch(1, 1)
        information_grid.setColumnStretch(3, 1)

        self.company_title_value = QLabel("-")
        self.tax_number_value = QLabel("-")
        self.sector_value = QLabel("-")
        self.activity_value = QLabel("-")
        self.nace_value = QLabel("-")
        self.erp_value = QLabel("-")
        self.inventory_value = QLabel("-")
        self.production_value = QLabel("-")
        self.service_value = QLabel("-")
        self.default_account_value = QLabel("-")

        self.add_information_row(
            information_grid,
            row=0,
            label_text="Unvan",
            value_label=self.company_title_value,
            column=0,
        )

        self.add_information_row(
            information_grid,
            row=1,
            label_text="VKN / TCKN",
            value_label=self.tax_number_value,
            column=0,
        )

        self.add_information_row(
            information_grid,
            row=2,
            label_text="Sektör",
            value_label=self.sector_value,
            column=0,
        )

        self.add_information_row(
            information_grid,
            row=3,
            label_text="Faaliyet",
            value_label=self.activity_value,
            column=0,
        )

        self.add_information_row(
            information_grid,
            row=4,
            label_text="NACE",
            value_label=self.nace_value,
            column=0,
        )

        self.add_information_row(
            information_grid,
            row=0,
            label_text="Stok Takibi",
            value_label=self.inventory_value,
            column=2,
        )

        self.add_information_row(
            information_grid,
            row=1,
            label_text="Üretim",
            value_label=self.production_value,
            column=2,
        )

        self.add_information_row(
            information_grid,
            row=2,
            label_text="Hizmet Üretimi",
            value_label=self.service_value,
            column=2,
        )

        self.add_information_row(
            information_grid,
            row=3,
            label_text="Muhasebe Programı",
            value_label=self.erp_value,
            column=2,
        )

        self.add_information_row(
            information_grid,
            row=4,
            label_text="Varsayılan Alış Hesabı",
            value_label=self.default_account_value,
            column=2,
        )

        layout.addLayout(information_grid)
        layout.addStretch()

        return frame

    def create_quick_actions_card(
        self,
    ) -> QFrame:
        frame = self.create_card()

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)

        title = QLabel("Hızlı İşlemler")
        title.setStyleSheet("""
            color: #172033;
            font-size: 16px;
            font-weight: 800;
        """)

        description = QLabel(
            "Aktarmak istediğiniz belge türünü seçin."
        )
        description.setStyleSheet("""
            color: #64748B;
            font-size: 12px;
        """)

        layout.addWidget(title)
        layout.addWidget(description)

        actions_grid = QGridLayout()
        actions_grid.setHorizontalSpacing(12)
        actions_grid.setVerticalSpacing(12)

        invoice_button = self.create_action_button(
            icon="▤",
            title="Fatura Aktarımı",
            description="PDF faturaları içe aktar",
            page_code="PDF Fatura",
            accent="#159A55",
            background="#F1FBF5",
        )

        bank_button = self.create_action_button(
            icon="▥",
            title="Banka Aktarımı",
            description="Hesap hareketlerini içe aktar",
            page_code="Belgeler",
            accent="#1769D2",
            background="#F1F6FE",
        )

        payroll_button = self.create_action_button(
            icon="♟",
            title="Bordro Aktarımı",
            description="Bordro belgelerini içe aktar",
            page_code="Belgeler",
            accent="#8B4CC2",
            background="#F8F2FD",
        )

        other_button = self.create_action_button(
            icon="▧",
            title="Diğer Belgeler",
            description="Diğer evrakları içe aktar",
            page_code="Belgeler",
            accent="#D88B12",
            background="#FFF8EC",
        )

        actions_grid.addWidget(
            invoice_button,
            0,
            0,
        )
        actions_grid.addWidget(
            bank_button,
            0,
            1,
        )
        actions_grid.addWidget(
            payroll_button,
            1,
            0,
        )
        actions_grid.addWidget(
            other_button,
            1,
            1,
        )

        actions_grid.setColumnStretch(0, 1)
        actions_grid.setColumnStretch(1, 1)

        layout.addLayout(actions_grid)
        layout.addStretch()

        return frame

    def create_action_button(
        self,
        *,
        icon: str,
        title: str,
        description: str,
        page_code: str,
        accent: str,
        background: str,
    ) -> QPushButton:
        button = QPushButton(
            f"{icon}    {title}\n"
            f"       {description}"
        )

        button.setMinimumHeight(88)
        button.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(
            lambda checked=False, code=page_code:
            self.page_requested.emit(code)
        )

        button.setStyleSheet(f"""
            QPushButton {{
                background: {background};
                color: #172033;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
                text-align: left;
                padding: 13px 15px;
                font-size: 12px;
                font-weight: 700;
            }}

            QPushButton:hover {{
                border: 1px solid {accent};
                background: white;
            }}

            QPushButton:pressed {{
                background: {background};
            }}

            QPushButton:disabled {{
                background: #F1F5F9;
                color: #94A3B8;
                border-color: #E2E8F0;
            }}
        """)

        button.setToolTip(title)

        self.quick_action_buttons.append(
            button
        )

        return button

    def create_workflow_card(
        self,
    ) -> QFrame:
        frame = self.create_card()

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(16)

        title = QLabel("MarkaAI İşlem Akışı")
        title.setStyleSheet("""
            color: #172033;
            font-size: 16px;
            font-weight: 800;
        """)

        subtitle = QLabel(
            "Belgeler kontrollü biçimde analiz edilir, "
            "mali müşavir onayından sonra muhasebe programına aktarılır."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("""
            color: #64748B;
            font-size: 12px;
        """)

        steps_layout = QHBoxLayout()
        steps_layout.setSpacing(8)

        steps = [
            ("1", "Belge Yükle"),
            ("2", "Firma ve İşlem Türünü Tanı"),
            ("3", "Muhasebe Fişini Oluştur"),
            ("4", "Kontrol ve Onay"),
            ("5", "ERP'ye Aktar"),
        ]

        for index, (
            number,
            text,
        ) in enumerate(steps):
            step_frame = QFrame()
            step_frame.setMinimumHeight(74)
            step_frame.setStyleSheet("""
                QFrame {
                    background: #F8FAFC;
                    border: 1px solid #E2E8F0;
                    border-radius: 9px;
                }
            """)

            step_layout = QVBoxLayout(step_frame)
            step_layout.setContentsMargins(
                10,
                10,
                10,
                10,
            )
            step_layout.setSpacing(5)

            number_label = QLabel(number)
            number_label.setAlignment(Qt.AlignCenter)
            number_label.setFixedSize(25, 25)
            number_label.setStyleSheet("""
                background: #1769D2;
                color: white;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 800;
            """)

            text_label = QLabel(text)
            text_label.setWordWrap(True)
            text_label.setAlignment(
                Qt.AlignCenter
            )
            text_label.setStyleSheet("""
                color: #334155;
                font-size: 10px;
                font-weight: 700;
            """)

            step_layout.addWidget(
                number_label,
                alignment=Qt.AlignCenter,
            )
            step_layout.addWidget(text_label)

            steps_layout.addWidget(
                step_frame,
                1,
            )

            if index < len(steps) - 1:
                arrow = QLabel("›")
                arrow.setAlignment(Qt.AlignCenter)
                arrow.setFixedWidth(15)
                arrow.setStyleSheet("""
                    color: #94A3B8;
                    font-size: 24px;
                    font-weight: bold;
                """)

                steps_layout.addWidget(arrow)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(steps_layout)

        return frame

    def create_card(self) -> QFrame:
        frame = QFrame()
        frame.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )
        frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #DFE6EF;
                border-radius: 12px;
            }
        """)

        return frame

    def add_information_row(
        self,
        grid: QGridLayout,
        *,
        row: int,
        label_text: str,
        value_label: QLabel,
        column: int,
    ):
        name_label = QLabel(label_text)
        name_label.setStyleSheet("""
            color: #64748B;
            font-size: 11px;
            border: none;
        """)

        value_label.setWordWrap(True)
        value_label.setStyleSheet("""
            color: #27364A;
            font-size: 11px;
            font-weight: 700;
            border: none;
        """)

        grid.addWidget(
            name_label,
            row,
            column,
        )
        grid.addWidget(
            value_label,
            row,
            column + 1,
        )

    def set_active_company(
        self,
        company: dict,
    ):
        """
        MainWindow tarafından seçilen firmayı ekranda gösterir.
        """

        self.active_company = company

        title = str(
            company.get(
                "title",
                "İsimsiz Firma",
            )
        ).strip()

        tax_number = str(
            company.get(
                "tax_number",
                "-",
            )
        ).strip()

        sector = str(
            company.get(
                "sector",
                "-",
            )
        ).strip() or "-"

        activity_types = company.get(
            "activity_types",
            [],
        )

        if not activity_types:
            activity_type = company.get(
                "activity_type",
                "",
            )

            if activity_type:
                activity_types = [
                    activity_type
                ]

        activity_names = [
            self.ACTIVITY_NAMES.get(
                activity,
                activity,
            )
            for activity in activity_types
            if activity
        ]

        activity_text = (
            ", ".join(activity_names)
            if activity_names
            else "-"
        )

        nace_codes = company.get(
            "nace_codes",
            [],
        )

        nace_text = (
            ", ".join(
                str(code)
                for code in nace_codes
            )
            if nace_codes
            else "-"
        )

        erp_code = str(
            company.get(
                "erp_system",
                "",
            )
        ).strip()

        erp_text = self.ERP_NAMES.get(
            erp_code,
            erp_code or "Tanımlanmadı",
        )

        default_accounts = company.get(
            "default_purchase_accounts",
            {},
        )

        default_account = self.get_default_account_text(
            company=company,
            default_accounts=default_accounts,
        )

        self.company_title_value.setText(title)
        self.tax_number_value.setText(tax_number)
        self.sector_value.setText(sector)
        self.activity_value.setText(
            activity_text
        )
        self.nace_value.setText(nace_text)
        self.erp_value.setText(erp_text)
        self.default_account_value.setText(
            default_account
        )

        self.set_status_label(
            self.inventory_value,
            bool(
                company.get(
                    "inventory_enabled",
                    False,
                )
            ),
        )

        self.set_status_label(
            self.production_value,
            bool(
                company.get(
                    "production_enabled",
                    False,
                )
            ),
        )

        self.set_status_label(
            self.service_value,
            bool(
                company.get(
                    "service_production_enabled",
                    False,
                )
            ),
        )

        self.page_title.setText(title)
        self.page_subtitle.setText(
            "Firma bilgileri ve hızlı muhasebe işlemleri"
        )

        self.active_company_badge.setText(
            "● Aktif Firma"
        )
        self.active_company_badge.setStyleSheet("""
            background: #EAF8EF;
            color: #138A4B;
            border-radius: 17px;
            padding: 0 15px;
            font-size: 12px;
            font-weight: 700;
        """)

        for button in self.quick_action_buttons:
            button.setEnabled(True)

    def clear_company_information(self):
        """
        Firma seçilmediğinde ekranı başlangıç durumuna getirir.
        """

        self.active_company = None

        information_labels = [
            self.company_title_value,
            self.tax_number_value,
            self.sector_value,
            self.activity_value,
            self.nace_value,
            self.erp_value,
            self.inventory_value,
            self.production_value,
            self.service_value,
            self.default_account_value,
        ]

        for label in information_labels:
            label.setText("-")
            label.setStyleSheet("""
                color: #94A3B8;
                font-size: 11px;
                font-weight: 700;
                border: none;
            """)

        self.page_title.setText(
            "Firma Paneli"
        )
        self.page_subtitle.setText(
            "İşleme başlamak için sol menüden firma seçin."
        )

        self.active_company_badge.setText(
            "Firma seçilmedi"
        )
        self.active_company_badge.setStyleSheet("""
            background: #E2E8F0;
            color: #64748B;
            border-radius: 17px;
            padding: 0 15px;
            font-size: 12px;
            font-weight: 700;
        """)

        for button in self.quick_action_buttons:
            button.setEnabled(False)

    def set_status_label(
        self,
        label: QLabel,
        enabled: bool,
    ):
        if enabled:
            label.setText("✓ Aktif")
            label.setStyleSheet("""
                color: #159A55;
                font-size: 11px;
                font-weight: 800;
                border: none;
            """)
        else:
            label.setText("○ Pasif")
            label.setStyleSheet("""
                color: #94A3B8;
                font-size: 11px;
                font-weight: 700;
                border: none;
            """)

    def get_default_account_text(
        self,
        *,
        company: dict,
        default_accounts: dict,
    ) -> str:
        primary_activity = company.get(
            "primary_activity_type",
            company.get(
                "activity_type",
                "",
            ),
        )

        if primary_activity == "manufacturing":
            account = default_accounts.get(
                "raw_material",
                "150",
            )
            return f"{account} - İlk Madde ve Malzeme"

        if primary_activity in {
            "trading",
            "export",
            "import",
        }:
            account = default_accounts.get(
                "trade_goods",
                "153",
            )
            return f"{account} - Ticari Mallar"

        if primary_activity == "service":
            account = default_accounts.get(
                "service_cost",
                default_accounts.get(
                    "direct_service_cost",
                    "740",
                ),
            )
            return f"{account} - Hizmet Üretim Maliyeti"

        return "İşleme göre belirlenecek"