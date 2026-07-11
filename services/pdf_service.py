import re
from pathlib import Path

import pymupdf


class PdfService:
    """
    PDF dosyalarını okur ve e-fatura metnindeki temel bilgileri ayıklar.
    """

    def read_text(self, pdf_path: str) -> str:
        """
        PDF'nin bütün sayfalarındaki metni tek bir metin olarak döndürür.
        """

        text_parts = []

        with pymupdf.open(pdf_path) as document:
            for page in document:
                page_text = page.get_text("text")
                text_parts.append(page_text)

        return "\n".join(text_parts).strip()

    def get_page_count(self, pdf_path: str) -> int:
        """
        PDF'nin sayfa sayısını döndürür.
        """

        with pymupdf.open(pdf_path) as document:
            return document.page_count

    def analyze_invoice(self, pdf_path: str) -> dict:
        """
        PDF'yi okuyarak temel fatura bilgilerini sözlük halinde döndürür.
        """

        text = self.read_text(pdf_path)

        return {
            "file_name": Path(pdf_path).name,
            "page_count": self.get_page_count(pdf_path),
            "invoice_number": self._find_value_after_label(
                text,
                r"Fatura\s*No"
            ),
            "invoice_date": self._find_value_after_label(
                text,
                r"Fatura\s*Tarihi"
            ),
            "invoice_type": self._find_value_after_label(
                text,
                r"Fatura\s*Tipi"
            ),
            "scenario": self._find_value_after_label(
                text,
                r"Senaryo"
            ),
            "seller_name": self._find_seller_name(text),
            "seller_tax_number": self._find_seller_tax_number(text),
            "buyer_name": self._find_buyer_name(text),
            "buyer_tax_number": self._find_buyer_tax_number(text),
            "subtotal": self._find_amount_after_label(
                text,
                r"Mal\s*Hizmet\s*Toplam\s*Tutarı"
            ),
            "vat_amount": self._find_amount_after_label(
                text,
                r"Hesaplanan\s*KDV(?:\s*\([^)]+\))?"
            ),
            "total_amount": self._find_amount_after_label(
                text,
                r"Vergiler\s*Dahil\s*Toplam\s*Tutar"
            ),
            "payable_amount": self._find_amount_after_label(
                text,
                r"Ödenecek\s*Tutar"
            ),
            "raw_text": text,
        }

    def _find_value_after_label(self, text: str, label_pattern: str) -> str:
        """
        Başlığın ardından gelen ilk dolu satırı bulur.

        Örnek:
        Fatura No:
        SNT2025000000031
        """

        pattern = rf"{label_pattern}\s*:?\s*\n+\s*([^\n]+)"

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if not match:
            return "-"

        return match.group(1).strip()

    def _find_amount_after_label(self, text: str, label_pattern: str) -> str:
        """
        Belirtilen başlığın ardından gelen Türkçe para tutarını bulur.
        """

        pattern = (
            rf"{label_pattern}\s*:?\s*\n+\s*"
            rf"([\d.]+,\d{{2}})\s*(?:TL|₺)?"
        )

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if not match:
            return "-"

        return f"{match.group(1)} TL"

    def _find_seller_name(self, text: str) -> str:
        """
        NOT bölümünden sonraki ilk anlamlı satırı satıcı adı olarak alır.
        """

        match = re.search(
            r"\bNOT\b\s*\n(?:.*\n)*?"
            r"(?!YALNIZ\s*:)([^\n]+)\s*\n"
            r"[^\n]*(?:MAH\.|CAD\.|SK\.|SOK\.|NO:)",
            text,
            flags=re.IGNORECASE
        )

        if not match:
            return "-"

        return match.group(1).strip()

    def _find_seller_tax_number(self, text: str) -> str:
        """
        ALICI başlığından önce bulunan TCKN veya VKN bilgisini döndürür.
        """

        seller_section = text.split("ALICI", maxsplit=1)[0]

        match = re.search(
            r"\b(?:TCKN|VKN)\s*:\s*(\d{10,11})",
            seller_section,
            flags=re.IGNORECASE
        )

        if not match:
            return "-"

        return match.group(1)

    def _find_buyer_name(self, text: str) -> str:
        """
        ALICI başlığından sonra adres satırına kadar olan firma adını bulur.
        """

        match = re.search(
            r"\bALICI\b\s*\n"
            r"(.+?)\n"
            r"[^\n]*(?:MAH\.|CAD\.|SK\.|SOK\.|NO:)",
            text,
            flags=re.IGNORECASE | re.DOTALL
        )

        if not match:
            return "-"

        buyer_name = match.group(1)

        buyer_name = re.sub(
            r"\s*\n\s*",
            " ",
            buyer_name
        )

        return buyer_name.strip()

    def _find_buyer_tax_number(self, text: str) -> str:
        """
        ALICI bölümündeki VKN veya TCKN bilgisini döndürür.
        """

        parts = re.split(
            r"\bALICI\b",
            text,
            maxsplit=1,
            flags=re.IGNORECASE
        )

        if len(parts) < 2:
            return "-"

        buyer_section = parts[1]

        match = re.search(
            r"\b(?:VKN|TCKN)\s*:\s*(\d{10,11})",
            buyer_section,
            flags=re.IGNORECASE
        )

        if not match:
            return "-"

        return match.group(1)