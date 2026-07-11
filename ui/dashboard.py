from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
)

from ui.widgets.card import Card
from ui.theme import Theme


class Dashboard(QWidget):

    page_requested = Signal(str)

    def __init__(self):
        super().__init__()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        title = QLabel("Hoş Geldiniz, Ali Osman")

        title.setStyleSheet(f"""
            font-size: {Theme.TITLE}px;
            font-weight: bold;
            color: {Theme.TEXT};
        """)

        subtitle = QLabel(
            "MarkaAI ile PDF faturalarını ve mizan dosyalarını analiz edebilirsiniz."
        )

        subtitle.setStyleSheet(f"""
            font-size: {Theme.NORMAL}px;
            color: {Theme.SUBTEXT};
        """)

        cards = QHBoxLayout()
        cards.setSpacing(20)

        pdf_card = Card(
            "📄 PDF Fatura Aktar",
            "PDF faturalarını okuyun ve muhasebe kayıt önerisi oluşturun.",
        )

        balance_card = Card(
            "📊 Mizan Analizi",
            "Excel veya PDF mizan dosyasını analiz edin.",
        )

        pdf_card.clicked.connect(
            lambda: self.page_requested.emit("PDF Fatura")
        )

        balance_card.clicked.connect(
            lambda: self.page_requested.emit("Mizan Analizi")
        )

        cards.addWidget(pdf_card)
        cards.addWidget(balance_card)
        cards.addStretch()

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addSpacing(20)
        main_layout.addLayout(cards)
        main_layout.addStretch()