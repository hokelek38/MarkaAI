from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from services.company_profile_service import CompanyProfileService
from ui.accounting_page import AccountingPage
from ui.company_dialog import CompanyDialog
from ui.dashboard import Dashboard
from ui.pdf_page import PdfPage
from ui.widgets.sidebar import Sidebar
from ui.widgets.topbar import TopBar


class MainWindow(QMainWindow):
    """
    MarkaAI ana uygulama penceresi.

    Görevleri:
    - Firma listesini yan menüye yüklemek
    - Aktif firmayı yönetmek
    - Yeni firma kayıt penceresini açmak
    - Sayfalar arasında geçiş yapmak
    - PDF analiz sonucunu muhasebe fişi ekranında göstermek
    """

    def __init__(self):
        super().__init__()

        self.setWindowTitle("MarkaAI")
        self.resize(1450, 900)

        self.company_service = CompanyProfileService()
        self.active_company_id = None
        self.active_company = None

        self.build_ui()
        self.connect_signals()
        self.load_companies()

        # Hiç firma yoksa program açılışında
        # firma kayıt ekranını otomatik açar.
        if not self.company_service.get_all_companies():
            QTimer.singleShot(
                250,
                self.open_company_dialog,
            )

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Sol menü
        self.sidebar = Sidebar()

        # Sağ içerik alanı
        right_widget = QWidget()

        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(16)

        self.topbar = TopBar()

        self.pages = QStackedWidget()

        # Aktif sayfalar
        self.home_page = Dashboard()
        self.pdf_page = PdfPage()
        self.accounting_page = AccountingPage()

        # Henüz geliştirilecek sayfalar
        self.mizan_page = self.create_placeholder_page(
            "Mizan Analizi",
            "Mizan yükleme ve analiz özellikleri geliştiriliyor.",
        )

        self.ai_page = self.create_placeholder_page(
            "AI Analiz",
            "Muhasebe karar ve risk analiz özellikleri geliştiriliyor.",
        )

        self.transfer_page = self.create_placeholder_page(
            "Aktarım",
            "Luca, Zirve, Logo ve diğer ERP aktarım bağlantıları geliştiriliyor.",
        )

        self.documents_page = self.create_placeholder_page(
            "Belgeler",
            "İşlenen faturalar ve oluşturulan muhasebe fişleri burada gösterilecek.",
        )

        self.settings_page = self.create_placeholder_page(
            "Ayarlar",
            "Firma, kullanıcı, lisans ve entegrasyon ayarları burada yönetilecek.",
        )

        self.pages.addWidget(self.home_page)
        self.pages.addWidget(self.pdf_page)
        self.pages.addWidget(self.accounting_page)
        self.pages.addWidget(self.mizan_page)
        self.pages.addWidget(self.ai_page)
        self.pages.addWidget(self.transfer_page)
        self.pages.addWidget(self.documents_page)
        self.pages.addWidget(self.settings_page)

        right_layout.addWidget(self.topbar)
        right_layout.addWidget(self.pages, 1)

        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(right_widget, 1)

        self.pages.setCurrentWidget(self.home_page)

    def connect_signals(self):
        """
        Uygulama içindeki sayfa ve firma sinyallerini bağlar.
        """

        self.sidebar.page_changed.connect(
            self.change_page
        )

        self.sidebar.company_changed.connect(
            self.change_company
        )

        self.sidebar.add_company_requested.connect(
            self.open_company_dialog
        )

        self.pdf_page.analysis_ready.connect(
            self.show_accounting_analysis
        )

        if hasattr(
            self.home_page,
            "page_requested",
        ):
            self.home_page.page_requested.connect(
                self.change_page
            )

    def load_companies(
        self,
        active_company_id: str | None = None,
    ):
        """
        Kayıtlı firmaları okuyup yan menüye gönderir.
        """

        companies = (
            self.company_service.get_all_companies(
                active_only=True
            )
        )

        if (
            active_company_id is None
            and self.active_company_id
        ):
            active_company_id = (
                self.active_company_id
            )

        if (
            active_company_id is None
            and companies
        ):
            active_company_id = companies[0].get(
                "company_id"
            )

        self.sidebar.set_companies(
            companies=companies,
            active_company_id=active_company_id,
            license_limit=len(companies),
        )

        if active_company_id:
            self.change_company(
                active_company_id
            )
        else:
            self.active_company_id = None
            self.active_company = None
            self.setWindowTitle("MarkaAI")

    def open_company_dialog(self):
        """
        Yeni firma kayıt penceresini açar.
        """

        dialog = CompanyDialog(
            parent=self,
            company_service=self.company_service,
        )

        result = dialog.exec()

        if result != CompanyDialog.Accepted:
            return

        created_company = (
            dialog.get_created_company()
        )

        if not created_company:
            return

        created_company_id = (
            created_company.get("company_id")
        )

        self.load_companies(
            active_company_id=created_company_id
        )

        self.pages.setCurrentWidget(
            self.home_page
        )

    def change_company(
        self,
        company_id: str,
    ):
        """
        Yan menüden seçilen firmayı aktif firma yapar.
        """

        company = self.company_service.find_company(
            company_id
        )

        if not company:
            QMessageBox.warning(
                self,
                "Firma Bulunamadı",
                "Seçilen firma kaydı bulunamadı.",
            )
            return

        self.active_company_id = company_id
        self.active_company = company

        # PDF işlemleri artık seçili firma üzerinden çalışır.
        self.pdf_page.company_id = company_id
        self.pdf_page.active_company = company

        # İleride sayfalara set_active_company metodu
        # eklendiğinde otomatik olarak aktif firma gönderilir.
        application_pages = [
            self.home_page,
            self.pdf_page,
            self.accounting_page,
            self.mizan_page,
            self.ai_page,
            self.transfer_page,
            self.documents_page,
            self.settings_page,
        ]

        for page in application_pages:
            set_company_method = getattr(
                page,
                "set_active_company",
                None,
            )

            if callable(set_company_method):
                set_company_method(company)

        company_title = company.get(
            "title",
            "Firma",
        )

        self.setWindowTitle(
            f"MarkaAI — {company_title}"
        )

    def change_page(
        self,
        page_code: str,
    ):
        """
        Yan menü veya dashboard üzerinden sayfa değiştirir.
        """

        page_map = {
            "Dashboard": self.home_page,
            "Ana Menü": self.home_page,
            "PDF Fatura": self.pdf_page,
            "PDF İşlemleri": self.pdf_page,
            "Mizan Analizi": self.mizan_page,
            "AI Analiz": self.ai_page,
            "Aktarım": self.transfer_page,
            "Belgeler": self.documents_page,
            "Ayarlar": self.settings_page,
            "Muhasebe Analizi": self.accounting_page,
        }

        target_page = page_map.get(page_code)

        if target_page is None:
            QMessageBox.information(
                self,
                "Sayfa Bulunamadı",
                f"{page_code} sayfası henüz tanımlanmadı.",
            )
            return

        # Firma gerektiren sayfalarda firma kontrolü
        if (
            target_page is not self.settings_page
            and not self.active_company_id
        ):
            QMessageBox.warning(
                self,
                "Firma Seçilmedi",
                "İşleme devam etmek için önce bir firma ekleyin veya seçin.",
            )
            return

        self.pages.setCurrentWidget(
            target_page
        )

    def show_accounting_analysis(
        self,
        voucher_data: dict,
        validation_result: dict,
    ):
        """
        PDF analizinden gelen muhasebe fişini
        Muhasebe Analizi sayfasına yükler.
        """

        try:
            self.accounting_page.load_voucher(
                voucher_data=voucher_data,
                validation_result=validation_result,
            )

            self.pages.setCurrentWidget(
                self.accounting_page
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Muhasebe Fişi Hatası",
                "Muhasebe fişi ekranda gösterilemedi:\n\n"
                f"{error}",
            )

    def create_placeholder_page(
        self,
        title_text: str,
        description_text: str,
    ) -> QWidget:
        """
        Henüz geliştirilmeyen menüler için geçici sayfa oluşturur.
        """

        page = QWidget()

        layout = QVBoxLayout(page)
        layout.setContentsMargins(
            35,
            35,
            35,
            35,
        )
        layout.setSpacing(12)
        layout.setAlignment(
            Qt.AlignTop
        )

        title = QLabel(title_text)
        title.setStyleSheet("""
            font-size: 26px;
            font-weight: bold;
            color: #1F2937;
        """)

        description = QLabel(
            description_text
        )
        description.setWordWrap(True)
        description.setStyleSheet("""
            font-size: 14px;
            color: #64748B;
            background: white;
            border: 1px solid #E5E7EB;
            border-radius: 10px;
            padding: 18px;
        """)

        layout.addWidget(title)
        layout.addWidget(description)

        return page