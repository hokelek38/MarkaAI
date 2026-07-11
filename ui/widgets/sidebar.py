from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class Sidebar(QWidget):
    """
    MarkaAI ana sol menüsü.

    Bölümler:
    - MarkaAI logosu ve adı
    - Firma listesi
    - Belge işlemleri
    - Ayarlar
    - Lisans ve sürüm bilgisi
    """

    page_changed = Signal(str)
    company_changed = Signal(str)
    add_company_requested = Signal()

    SIDEBAR_WIDTH = 255

    def __init__(self):
        super().__init__()

        self.companies = []
        self.company_buttons = {}
        self.navigation_buttons = []
        self.active_company_id = None

        self.setObjectName("Sidebar")
        self.setFixedWidth(self.SIDEBAR_WIDTH)
        self.setMinimumHeight(600)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.setStyleSheet("""
            QWidget#Sidebar {
                background: #071B34;
            }
        """)

        self.build_ui()

    def build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Marka alanı sabit kalır.
        root_layout.addWidget(
            self.create_brand_area()
        )

        # Menü içeriği kaydırılabilir.
        menu_scroll = QScrollArea()
        menu_scroll.setWidgetResizable(True)
        menu_scroll.setFrameShape(QFrame.NoFrame)
        menu_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        menu_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )
        menu_scroll.setStyleSheet("""
            QScrollArea {
                background: #071B34;
                border: none;
            }

            QScrollBar:vertical {
                background: #071B34;
                width: 7px;
                margin: 2px;
            }

            QScrollBar::handle:vertical {
                background: #34506F;
                border-radius: 3px;
                min-height: 30px;
            }

            QScrollBar::handle:vertical:hover {
                background: #4B6B8F;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        menu_widget = QWidget()
        menu_widget.setAttribute(
            Qt.WA_StyledBackground,
            True,
        )
        menu_widget.setStyleSheet("""
            background: #071B34;
        """)

        menu_layout = QVBoxLayout(menu_widget)
        menu_layout.setContentsMargins(12, 10, 12, 12)
        menu_layout.setSpacing(8)

        self.build_company_section(menu_layout)
        self.add_section_spacing(menu_layout)
        self.build_documents_section(menu_layout)
        self.add_section_spacing(menu_layout)
        self.build_settings_section(menu_layout)

        menu_layout.addStretch()

        menu_scroll.setWidget(menu_widget)
        root_layout.addWidget(menu_scroll, 1)

        # Lisans ve sürüm alanı sabit kalır.
        root_layout.addWidget(
            self.create_footer()
        )

    def create_brand_area(self) -> QWidget:
        brand_widget = QWidget()
        brand_widget.setFixedHeight(82)
        brand_widget.setAttribute(
            Qt.WA_StyledBackground,
            True,
        )
        brand_widget.setStyleSheet("""
            background: #071B34;
            border-bottom: 1px solid #183553;
        """)

        layout = QHBoxLayout(brand_widget)
        layout.setContentsMargins(18, 14, 14, 14)
        layout.setSpacing(12)

        logo_label = QLabel()
        logo_label.setFixedSize(48, 48)
        logo_label.setAlignment(Qt.AlignCenter)

        project_root = (
            Path(__file__).resolve().parents[2]
        )
        logo_path = project_root / "assets" / "logo.png"

        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))

            if not pixmap.isNull():
                logo_label.setPixmap(
                    pixmap.scaled(
                        44,
                        44,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
        else:
            # Logo dosyası eklenene kadar geçici MarkaAI simgesi.
            logo_label.setText("M")
            logo_label.setStyleSheet("""
                QLabel {
                    background: #EAF2FF;
                    color: #1769D2;
                    border-radius: 13px;
                    font-size: 25px;
                    font-weight: 900;
                }
            """)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 2, 0, 2)
        text_layout.setSpacing(1)

        brand_name = QLabel("MarkaAI")
        brand_name.setStyleSheet("""
            color: white;
            font-size: 21px;
            font-weight: 800;
        """)

        brand_description = QLabel(
            "Akıllı Muhasebe Asistanı"
        )
        brand_description.setStyleSheet("""
            color: #A8BCD2;
            font-size: 9px;
        """)

        text_layout.addWidget(brand_name)
        text_layout.addWidget(brand_description)

        layout.addWidget(logo_label)
        layout.addLayout(text_layout)
        layout.addStretch()

        return brand_widget

    def build_company_section(
        self,
        parent_layout: QVBoxLayout,
    ):
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(7, 0, 5, 0)

        title = self.create_section_title(
            "FİRMALAR"
        )

        self.company_count_label = QLabel("0")
        self.company_count_label.setAlignment(
            Qt.AlignCenter
        )
        self.company_count_label.setFixedSize(25, 20)
        self.company_count_label.setStyleSheet("""
            background: #163555;
            color: #BBD0E5;
            border-radius: 10px;
            font-size: 10px;
            font-weight: bold;
        """)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(
            self.company_count_label
        )

        parent_layout.addLayout(header_layout)

        self.company_search = QLineEdit()
        self.company_search.setPlaceholderText(
            "Firma ara..."
        )
        self.company_search.setClearButtonEnabled(True)
        self.company_search.setFixedHeight(36)
        self.company_search.textChanged.connect(
            self.filter_companies
        )
        self.company_search.setStyleSheet("""
            QLineEdit {
                background: #102D4B;
                color: white;
                border: 1px solid #294866;
                border-radius: 7px;
                padding: 0 10px;
                font-size: 12px;
            }

            QLineEdit:focus {
                border-color: #2781E7;
            }

            QLineEdit::placeholder {
                color: #7792AE;
            }
        """)

        parent_layout.addWidget(
            self.company_search
        )

        self.add_company_button = QPushButton(
            "＋  Yeni Firma Ekle"
        )
        self.add_company_button.setFixedHeight(35)
        self.add_company_button.setCursor(
            Qt.PointingHandCursor
        )
        self.add_company_button.clicked.connect(
            self.add_company_requested.emit
        )
        self.add_company_button.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #72B7FF;
                border: 1px dashed #2C76BF;
                border-radius: 7px;
                text-align: left;
                padding-left: 10px;
                font-size: 12px;
                font-weight: 600;
            }

            QPushButton:hover {
                background: #123B63;
                color: white;
            }

            QPushButton:pressed {
                background: #154C7D;
            }
        """)

        parent_layout.addWidget(
            self.add_company_button
        )

        # Firma listesi kendi içinde kayar.
        self.company_scroll = QScrollArea()
        self.company_scroll.setWidgetResizable(True)
        self.company_scroll.setFrameShape(QFrame.NoFrame)
        self.company_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        self.company_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )
        self.company_scroll.setMinimumHeight(115)
        self.company_scroll.setMaximumHeight(245)
        self.company_scroll.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )
        self.company_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }

            QScrollBar:vertical {
                background: transparent;
                width: 6px;
            }

            QScrollBar::handle:vertical {
                background: #3C5D7E;
                border-radius: 3px;
                min-height: 25px;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        self.company_list_widget = QWidget()
        self.company_list_widget.setStyleSheet("""
            background: transparent;
        """)

        self.company_list_layout = QVBoxLayout(
            self.company_list_widget
        )
        self.company_list_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        self.company_list_layout.setSpacing(5)
        self.company_list_layout.addStretch()

        self.company_scroll.setWidget(
            self.company_list_widget
        )

        parent_layout.addWidget(
            self.company_scroll
        )

    def build_documents_section(
        self,
        parent_layout: QVBoxLayout,
    ):
        parent_layout.addWidget(
            self.create_section_title("BELGELER")
        )

        self.create_navigation_button(
            parent_layout,
            icon="▣",
            visible_text="PDF Faturalar",
            page_code="PDF Fatura",
        )

        self.create_navigation_button(
            parent_layout,
            icon="▤",
            visible_text="Muhasebe Fişleri",
            page_code="Muhasebe Analizi",
        )

        self.create_navigation_button(
            parent_layout,
            icon="▥",
            visible_text="Banka Hareketleri",
            page_code="Belgeler",
        )

        self.create_navigation_button(
            parent_layout,
            icon="◫",
            visible_text="Bordro Belgeleri",
            page_code="Belgeler",
        )

        self.create_navigation_button(
            parent_layout,
            icon="◇",
            visible_text="Arşiv",
            page_code="Belgeler",
        )

    def build_settings_section(
        self,
        parent_layout: QVBoxLayout,
    ):
        parent_layout.addWidget(
            self.create_section_title("AYARLAR")
        )

        self.create_navigation_button(
            parent_layout,
            icon="⚙",
            visible_text="Firma Ayarları",
            page_code="Ayarlar",
        )

        self.create_navigation_button(
            parent_layout,
            icon="≡",
            visible_text="Hesap Planı",
            page_code="Ayarlar",
        )

        self.create_navigation_button(
            parent_layout,
            icon="♙",
            visible_text="Kullanıcılar",
            page_code="Ayarlar",
        )

        self.create_navigation_button(
            parent_layout,
            icon="⌘",
            visible_text="Entegrasyonlar",
            page_code="Ayarlar",
        )

        self.create_navigation_button(
            parent_layout,
            icon="◉",
            visible_text="Genel Ayarlar",
            page_code="Ayarlar",
        )

    def create_section_title(
        self,
        text: str,
    ) -> QLabel:
        label = QLabel(text)
        label.setFixedHeight(24)
        label.setStyleSheet("""
            color: #B7C8DA;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1px;
            padding-left: 7px;
        """)

        return label

    def add_section_spacing(
        self,
        layout: QVBoxLayout,
    ):
        spacer = QWidget()
        spacer.setFixedHeight(8)
        layout.addWidget(spacer)

    def create_footer(self) -> QWidget:
        footer = QWidget()
        footer.setFixedHeight(65)
        footer.setAttribute(
            Qt.WA_StyledBackground,
            True,
        )
        footer.setStyleSheet("""
            background: #071B34;
            border-top: 1px solid #183553;
        """)

        layout = QVBoxLayout(footer)
        layout.setContentsMargins(18, 8, 12, 8)
        layout.setSpacing(2)

        self.license_label = QLabel(
            "Aktif Firma: 0 / 0"
        )
        self.license_label.setStyleSheet("""
            color: #A8BCD2;
            font-size: 10px;
        """)

        version_label = QLabel("MarkaAI v0.5")
        version_label.setStyleSheet("""
            color: #607C98;
            font-size: 10px;
        """)

        layout.addWidget(self.license_label)
        layout.addWidget(version_label)

        return footer

    def set_companies(
        self,
        companies: list[dict],
        active_company_id: str | None = None,
        license_limit: int | None = None,
    ):
        """
        Firma listesini yeniler.
        """

        self.companies = [
            company
            for company in companies
            if company.get("active", True)
        ]

        self.clear_company_buttons()

        for company in self.companies:
            self.create_company_button(company)

        company_count = len(self.companies)

        self.company_count_label.setText(
            str(company_count)
        )

        if license_limit is None:
            license_limit = company_count

        self.license_label.setText(
            f"Aktif Firma: {company_count} / {license_limit}"
        )

        selected_company_id = active_company_id

        if (
            not selected_company_id
            and self.companies
        ):
            selected_company_id = (
                self.companies[0].get(
                    "company_id"
                )
            )

        if selected_company_id:
            self.select_company(
                selected_company_id,
                emit_signal=False,
                open_dashboard=False,
            )

    def create_company_button(
        self,
        company: dict,
    ):
        company_id = str(
            company.get("company_id", "")
        ).strip()

        if not company_id:
            return

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
                activity_types = [activity_type]

        activity_names = [
            self.get_activity_name(
                activity_type
            )
            for activity_type in activity_types
            if activity_type
        ]

        activity_text = ", ".join(
            activity_names
        )

        button_text = f"▦   {title}"

        if activity_text:
            button_text += (
                f"\n      {activity_text}"
            )

        button = QPushButton(button_text)
        button.setCheckable(True)
        button.setMinimumHeight(51)
        button.setMaximumHeight(58)
        button.setCursor(Qt.PointingHandCursor)
        button.setProperty(
            "company_id",
            company_id,
        )
        button.setProperty(
            "search_text",
            (
                f"{title} {tax_number} "
                f"{activity_text}"
            ).casefold(),
        )

        button.setToolTip(
            f"{title}\n"
            f"VKN/TCKN: {tax_number}\n"
            f"Faaliyet: {activity_text or '-'}"
        )

        button.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #C9D6E4;
                border: 1px solid transparent;
                border-radius: 7px;
                text-align: left;
                padding: 7px 8px;
                font-size: 11px;
            }

            QPushButton:hover {
                background: #143A5E;
                color: white;
            }

            QPushButton:checked {
                background: #1769D2;
                color: white;
                border-color: #3287ED;
                font-weight: 700;
            }

            QPushButton:pressed {
                background: #1458AE;
            }
        """)

        button.clicked.connect(
            lambda checked=False, cid=company_id:
            self.select_company(
                cid,
                emit_signal=True,
                open_dashboard=True,
            )
        )

        insert_index = (
            self.company_list_layout.count() - 1
        )

        self.company_list_layout.insertWidget(
            insert_index,
            button,
        )

        self.company_buttons[
            company_id
        ] = button

    def select_company(
        self,
        company_id: str,
        emit_signal: bool = True,
        open_dashboard: bool = False,
    ):
        """
        Seçilen firmayı aktif hale getirir.
        """

        if company_id not in self.company_buttons:
            return

        self.active_company_id = company_id

        for current_id, button in (
            self.company_buttons.items()
        ):
            button.setChecked(
                current_id == company_id
            )

        if emit_signal:
            self.company_changed.emit(
                company_id
            )

        if open_dashboard:
            self.clear_navigation_selection()
            self.page_changed.emit(
                "Dashboard"
            )

    def filter_companies(
        self,
        search_text: str,
    ):
        """
        Unvan, VKN/TCKN ve faaliyet türüne göre süzer.
        """

        normalized_search = (
            search_text.strip().casefold()
        )

        for button in self.company_buttons.values():
            search_value = str(
                button.property(
                    "search_text"
                )
                or ""
            )

            button.setVisible(
                not normalized_search
                or normalized_search
                in search_value
            )

    def clear_company_buttons(self):
        """
        Firma listesindeki mevcut butonları kaldırır.
        """

        for button in self.company_buttons.values():
            self.company_list_layout.removeWidget(
                button
            )
            button.deleteLater()

        self.company_buttons.clear()
        self.active_company_id = None

    def create_navigation_button(
        self,
        layout: QVBoxLayout,
        *,
        icon: str,
        visible_text: str,
        page_code: str,
    ):
        button = QPushButton(
            f"{icon}   {visible_text}"
        )
        button.setCheckable(True)
        button.setFixedHeight(37)
        button.setCursor(Qt.PointingHandCursor)

        button.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #C2D0DF;
                border: none;
                border-radius: 7px;
                text-align: left;
                padding-left: 10px;
                font-size: 11px;
            }

            QPushButton:hover {
                background: #143A5E;
                color: white;
            }

            QPushButton:checked {
                background: #1769D2;
                color: white;
                font-weight: 700;
            }

            QPushButton:pressed {
                background: #1458AE;
            }
        """)

        button.clicked.connect(
            lambda checked=False, selected=button:
            self.set_active_navigation_button(
                selected
            )
        )

        button.clicked.connect(
            lambda checked=False, code=page_code:
            self.page_changed.emit(code)
        )

        layout.addWidget(button)
        self.navigation_buttons.append(button)

    def set_active_navigation_button(
        self,
        active_button: QPushButton,
    ):
        for button in self.navigation_buttons:
            button.setChecked(
                button is active_button
            )

    def clear_navigation_selection(self):
        for button in self.navigation_buttons:
            button.setChecked(False)

    def get_active_company_id(
        self,
    ) -> str | None:
        return self.active_company_id

    def get_activity_name(
        self,
        activity_type: str,
    ) -> str:
        activity_names = {
            "manufacturing": "İmalat",
            "trading": "Ticaret",
            "service": "Hizmet",
            "export": "İhracat",
            "import": "İthalat",
        }

        return activity_names.get(
            activity_type,
            activity_type,
        )