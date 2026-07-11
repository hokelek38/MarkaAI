import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pymupdf


class PdfService:
    """
    PDF dosyalarını okur ve e-fatura metinlerinden
    bir veya birden fazla faturayı ayırarak analiz eder.
    """

    def read_pages(self, pdf_path: str) -> list[str]:
        """
        PDF sayfalarının metinlerini ayrı ayrı döndürür.
        """

        page_texts = []

        with pymupdf.open(pdf_path) as document:
            for page in document:
                page_text = page.get_text("text").strip()
                page_texts.append(page_text)

        return page_texts

    def read_text(self, pdf_path: str) -> str:
        """
        PDF'nin bütün sayfalarındaki metni tek metin olarak döndürür.
        """

        return "\n".join(
            self.read_pages(pdf_path)
        ).strip()

    def get_page_count(self, pdf_path: str) -> int:
        """
        PDF'nin toplam sayfa sayısını döndürür.
        """

        with pymupdf.open(pdf_path) as document:
            return document.page_count

    def analyze_invoice(self, pdf_path: str) -> dict:
        """
        Geriye uyumluluk için ilk faturayı döndürür.

        Birden fazla fatura bulunursa:
        - İlk fatura döndürülür.
        - invoice_count alanında toplam fatura sayısı gösterilir.

        Birleşik PDF işlemlerinde analyze_invoices() kullanılmalıdır.
        """

        invoices = self.analyze_invoices(pdf_path)

        if not invoices:
            raise ValueError(
                "PDF içinde analiz edilebilecek bir fatura bulunamadı."
            )

        first_invoice = invoices[0].copy()
        first_invoice["invoice_count"] = len(invoices)

        return first_invoice

    def analyze_invoices(self, pdf_path: str) -> list[dict]:
        """
        PDF içindeki faturaları birbirinden ayırarak analiz eder.

        Ayırma işlemi öncelikle:
        - Fatura numarası
        - ETTN / UUID

        bilgileri üzerinden yapılır.
        """

        pdf_file = Path(pdf_path)

        if not pdf_file.exists():
            raise FileNotFoundError(
                f"PDF dosyası bulunamadı: {pdf_path}"
            )

        page_texts = self.read_pages(pdf_path)
        document_page_count = len(page_texts)

        if not page_texts:
            raise ValueError(
                "PDF dosyasında okunabilir sayfa bulunamadı."
            )

        invoice_groups = self._group_pages_by_invoice(
            page_texts
        )

        invoices = []
        invoice_count = len(invoice_groups)

        for invoice_index, group in enumerate(
            invoice_groups,
            start=1,
        ):
            combined_text = "\n".join(
                group["texts"]
            ).strip()

            invoice_data = self._analyze_invoice_text(
                text=combined_text,
                file_name=pdf_file.name,
                invoice_index=invoice_index,
                invoice_count=invoice_count,
                document_page_count=document_page_count,
                page_numbers=group["page_numbers"],
            )

            invoices.append(invoice_data)

        return invoices

    def _group_pages_by_invoice(
        self,
        page_texts: list[str],
    ) -> list[dict]:
        """
        Sayfaları fatura numarası veya ETTN değişimine göre gruplar.

        Aynı fatura numarasına sahip ardışık sayfalar tek fatura kabul edilir.
        Fatura numarası olmayan devam sayfaları mevcut faturaya eklenir.
        """

        groups = []

        current_group = None

        for page_index, page_text in enumerate(
            page_texts,
            start=1,
        ):
            invoice_identity = (
                self._find_invoice_identity(page_text)
            )

            page_looks_like_invoice = (
                self._looks_like_invoice_page(page_text)
            )

            if current_group is None:
                current_group = {
                    "identity": invoice_identity,
                    "texts": [page_text],
                    "page_numbers": [page_index],
                    "looks_like_invoice": page_looks_like_invoice,
                }
                continue

            current_identity = current_group["identity"]

            should_start_new_group = False

            # Her iki sayfada da fatura kimliği varsa
            # ve kimlikler farklıysa yeni fatura başlar.
            if (
                invoice_identity
                and current_identity
                and invoice_identity != current_identity
            ):
                should_start_new_group = True

            # Önceki sayfada kimlik bulunamadıysa fakat
            # önceki sayfa fatura başlangıcı gibi görünüyorsa ve
            # yeni sayfada farklı bir fatura kimliği bulunduysa,
            # yeni grup başlatılır.
            elif (
                invoice_identity
                and not current_identity
                and current_group["looks_like_invoice"]
            ):
                should_start_new_group = True

            if should_start_new_group:
                groups.append(current_group)

                current_group = {
                    "identity": invoice_identity,
                    "texts": [page_text],
                    "page_numbers": [page_index],
                    "looks_like_invoice": page_looks_like_invoice,
                }

            else:
                current_group["texts"].append(page_text)
                current_group["page_numbers"].append(
                    page_index
                )

                if (
                    not current_group["identity"]
                    and invoice_identity
                ):
                    current_group["identity"] = (
                        invoice_identity
                    )

                if page_looks_like_invoice:
                    current_group["looks_like_invoice"] = True

        if current_group is not None:
            groups.append(current_group)

        return groups

    def _find_invoice_identity(
        self,
        text: str,
    ) -> str | None:
        """
        Sayfanın hangi faturaya ait olduğunu belirleyen kimliği döndürür.

        Öncelik:
        1. Fatura numarası
        2. ETTN / UUID
        """

        invoice_number = self._find_first_value(
            text,
            [
                r"Fatura\s*No",
                r"Fatura\s*Numarası",
                r"Belge\s*No",
            ],
        )

        if invoice_number != "-":
            normalized_number = self._normalize_identity(
                invoice_number
            )

            if normalized_number:
                return f"INVOICE:{normalized_number}"

        ettn = self._find_first_value(
            text,
            [
                r"ETTN",
                r"UUID",
            ],
        )

        if ettn != "-":
            normalized_ettn = self._normalize_identity(
                ettn
            )

            if normalized_ettn:
                return f"ETTN:{normalized_ettn}"

        return None

    def _normalize_identity(
        self,
        value: str,
    ) -> str:
        """
        Fatura numarası ve ETTN gibi kimlikleri karşılaştırılabilir hale getirir.
        """

        return re.sub(
            r"[^A-Z0-9]",
            "",
            str(value).upper(),
        )

    def _looks_like_invoice_page(
        self,
        text: str,
    ) -> bool:
        """
        Sayfanın fatura başlangıcı olup olmadığını yaklaşık olarak belirler.
        """

        invoice_markers = [
            r"\bFatura\s*No\b",
            r"\bFatura\s*Tarihi\b",
            r"\bFatura\s*Tipi\b",
            r"\bÖdenecek\s*Tutar\b",
            r"\bVergiler\s*Dahil\s*Toplam\s*Tutar\b",
            r"\bETTN\b",
        ]

        matched_marker_count = 0

        for marker in invoice_markers:
            if re.search(
                marker,
                text,
                flags=re.IGNORECASE,
            ):
                matched_marker_count += 1

        return matched_marker_count >= 2

    def _analyze_invoice_text(
        self,
        *,
        text: str,
        file_name: str,
        invoice_index: int,
        invoice_count: int,
        document_page_count: int,
        page_numbers: list[int],
    ) -> dict:
        """
        Tek faturaya ait birleştirilmiş metni analiz eder.
        """

        invoice_number = self._find_first_value(
            text,
            [
                r"Fatura\s*No",
                r"Fatura\s*Numarası",
                r"Belge\s*No",
            ],
        )

        invoice_date = self._find_first_value(
            text,
            [
                r"Fatura\s*Tarihi",
                r"Düzenleme\s*Tarihi",
                r"Belge\s*Tarihi",
            ],
        )

        ettn = self._find_first_value(
            text,
            [
                r"ETTN",
                r"UUID",
            ],
        )

        return {
            "file_name": file_name,
            "invoice_index": invoice_index,
            "invoice_count": invoice_count,
            "page_count": len(page_numbers),
            "document_page_count": document_page_count,
            "page_numbers": page_numbers,
            "page_range": self._format_page_range(
                page_numbers
            ),
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "invoice_type": self._find_first_value(
                text,
                [
                    r"Fatura\s*Tipi",
                    r"Belge\s*Tipi",
                ],
            ),
            "scenario": self._find_first_value(
                text,
                [
                    r"Senaryo",
                ],
            ),
            "ettn": ettn,
            "seller_name": self._find_seller_name(
                text
            ),
            "seller_tax_number": (
                self._find_seller_tax_number(text)
            ),
            "buyer_name": self._find_buyer_name(
                text
            ),
            "buyer_tax_number": (
                self._find_buyer_tax_number(text)
            ),
            "tax_base_amount": self._find_tax_base_amount(
                text
            ),
            "subtotal": self._find_first_amount(
                text,
                [
                    r"Mal\s*Hizmet\s*Toplam\s*Tutarı",
                    r"Mal\s*Hizmet\s*Toplamı",
                    r"Ara\s*Toplam",
                ],
            ),
            "vat_amount": self._find_first_amount(
                text,
                [
                    r"Hesaplanan\s*KDV(?:\s*\([^)]+\))?",
                    r"KDV\s*Tutarı",
                    r"Toplam\s*KDV",
                ],
            ),
            "total_amount": self._find_first_amount(
                text,
                [
                    r"Vergiler\s*Dahil\s*Toplam\s*Tutar",
                    r"Genel\s*Toplam",
                ],
            ),
            "payable_amount": self._find_first_amount(
                text,
                [
                    r"Ödenecek\s*Tutar",
                    r"Ödenecek\s*Toplam",
                ],
            ),
            "raw_text": text,
        }

    def _find_tax_base_amount(
        self,
        text: str,
    ) -> str:
        """
        Faturadaki KDV matrah toplamını bulur.

        Öncelik:
        1. Açıkça yazılmış toplam matrah
        2. Farklı KDV oranlarına ait matrahların toplamı
        3. Mal/hizmet toplamı yedek değeri
        """

        explicit_total = self._find_first_amount(
            text,
            [
                r"Toplam\s*KDV\s*Matrahı",
                r"KDV\s*Matrah\s*Toplamı",
                r"Toplam\s*Matrah",
                r"Matrah\s*Toplamı",
                r"Vergi\s*Matrahı",
            ],
        )

        if explicit_total != "-":
            return explicit_total

        tax_bases = self._find_all_amounts_after_label(
            text,
            (
                r"KDV\s*Matrahı"
                r"(?:\s*\([^)]+\))?"
            ),
        )

        if tax_bases:
            total = sum(
                (
                    self._amount_to_decimal(amount)
                    for amount in tax_bases
                ),
                Decimal("0.00"),
            )

            if total > Decimal("0.00"):
                return self._decimal_to_turkish_amount(
                    total
                )

        # Matrah ayrı gösterilmiyorsa geçici olarak
        # mal/hizmet toplamına dönülür.
        return self._find_first_amount(
            text,
            [
                r"Mal\s*Hizmet\s*Toplam\s*Tutarı",
                r"Mal\s*Hizmet\s*Toplamı",
                r"Ara\s*Toplam",
            ],
        )

    def _find_all_amounts_after_label(
        self,
        text: str,
        label_pattern: str,
    ) -> list[str]:
        """
        Aynı başlığa ait tüm tutarları bulur.
        Çok oranlı KDV faturalarında kullanılır.
        """

        amount_pattern = (
            r"("
            r"\d{1,3}(?:\.\d{3})*,\d{2}"
            r"|"
            r"\d+,\d{2}"
            r"|"
            r"\d+\.\d{2}"
            r")"
        )

        pattern = (
            rf"{label_pattern}\s*:?\s*"
            rf"(?:\n+\s*)?"
            rf"{amount_pattern}\s*(?:TL|₺)?"
        )

        return [
            match.group(1)
            for match in re.finditer(
                pattern,
                text,
                flags=re.IGNORECASE,
            )
        ]

    def _amount_to_decimal(
        self,
        value,
    ) -> Decimal:
        """
        Türkçe ve standart tutarları Decimal'e dönüştürür.
        """

        normalized = (
            str(value)
            .replace("TL", "")
            .replace("₺", "")
            .replace(" ", "")
            .strip()
        )

        if not normalized or normalized == "-":
            return Decimal("0.00")

        if "," in normalized:
            normalized = (
                normalized
                .replace(".", "")
                .replace(",", ".")
            )

        try:
            return Decimal(normalized)

        except InvalidOperation as error:
            raise ValueError(
                f"Geçersiz fatura tutarı: {value}"
            ) from error

    def _decimal_to_turkish_amount(
        self,
        value: Decimal,
    ) -> str:
        """
        Decimal tutarı Türkçe para biçimine dönüştürür.
        """

        value = value.quantize(
            Decimal("0.01")
        )

        standard = f"{value:,.2f}"

        turkish = (
            standard
            .replace(",", "_")
            .replace(".", ",")
            .replace("_", ".")
        )

        return f"{turkish} TL"

    def _format_page_range(
        self,
        page_numbers: list[int],
    ) -> str:
        """
        Sayfa numaralarını okunabilir metne dönüştürür.
        """

        if not page_numbers:
            return "-"

        if len(page_numbers) == 1:
            return str(page_numbers[0])

        return (
            f"{page_numbers[0]}-{page_numbers[-1]}"
        )

    def _find_first_value(
        self,
        text: str,
        label_patterns: list[str],
    ) -> str:
        """
        Birden fazla başlık seçeneği içinden ilk bulunan değeri döndürür.
        """

        for label_pattern in label_patterns:
            value = self._find_value_after_label(
                text,
                label_pattern,
            )

            if value != "-":
                return value

        return "-"

    def _find_first_amount(
        self,
        text: str,
        label_patterns: list[str],
    ) -> str:
        """
        Birden fazla tutar başlığından ilk bulunan tutarı döndürür.
        """

        for label_pattern in label_patterns:
            amount = self._find_amount_after_label(
                text,
                label_pattern,
            )

            if amount != "-":
                return amount

        return "-"

    def _find_value_after_label(
        self,
        text: str,
        label_pattern: str,
    ) -> str:
        """
        Başlığın aynı satırında veya sonraki satırında bulunan değeri döndürür.

        Desteklenen örnekler:

        Fatura No: SNT2025000000031

        Fatura No:
        SNT2025000000031
        """

        patterns = [
            (
                rf"{label_pattern}\s*:?\s*"
                rf"([^\n\r]+)"
            ),
            (
                rf"{label_pattern}\s*:?\s*"
                rf"\n+\s*([^\n\r]+)"
            ),
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            value = match.group(1).strip()

            value = re.sub(
                r"\s+",
                " ",
                value,
            )

            if value:
                return value

        return "-"

    def _find_amount_after_label(
        self,
        text: str,
        label_pattern: str,
    ) -> str:
        """
        Başlığın aynı satırında veya sonraki satırında bulunan tutarı döndürür.
        """

        amount_pattern = (
            r"("
            r"\d{1,3}(?:\.\d{3})*,\d{2}"
            r"|"
            r"\d+,\d{2}"
            r"|"
            r"\d+\.\d{2}"
            r")"
        )

        patterns = [
            (
                rf"{label_pattern}\s*:?\s*"
                rf"{amount_pattern}\s*(?:TL|₺)?"
            ),
            (
                rf"{label_pattern}\s*:?\s*"
                rf"\n+\s*{amount_pattern}\s*(?:TL|₺)?"
            ),
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:
                return f"{match.group(1)} TL"

        return "-"

    def _find_seller_name(
        self,
        text: str,
    ) -> str:
        """
        NOT bölümünden sonraki ilk anlamlı satırı satıcı adı olarak alır.
        """

        match = re.search(
            r"\bNOT\b\s*\n(?:.*\n)*?"
            r"(?!YALNIZ\s*:)([^\n]+)\s*\n"
            r"[^\n]*(?:MAH\.|CAD\.|SK\.|SOK\.|NO:)",
            text,
            flags=re.IGNORECASE,
        )

        if not match:
            return "-"

        return match.group(1).strip()

    def _find_seller_tax_number(
        self,
        text: str,
    ) -> str:
        """
        ALICI başlığından önce bulunan TCKN veya VKN bilgisini döndürür.
        """

        seller_section = re.split(
            r"\bALICI\b",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        match = re.search(
            r"\b(?:TCKN|VKN)\s*:\s*(\d{10,11})",
            seller_section,
            flags=re.IGNORECASE,
        )

        if not match:
            return "-"

        return match.group(1)

    def _find_buyer_name(
        self,
        text: str,
    ) -> str:
        """
        ALICI başlığından sonra adres satırına kadar olan firma adını bulur.
        """

        match = re.search(
            r"\bALICI\b\s*\n"
            r"(.+?)\n"
            r"[^\n]*(?:MAH\.|CAD\.|SK\.|SOK\.|NO:)",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if not match:
            return "-"

        buyer_name = match.group(1)

        buyer_name = re.sub(
            r"\s*\n\s*",
            " ",
            buyer_name,
        )

        return buyer_name.strip()

    def _find_buyer_tax_number(
        self,
        text: str,
    ) -> str:
        """
        ALICI bölümündeki VKN veya TCKN bilgisini döndürür.
        """

        parts = re.split(
            r"\bALICI\b",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )

        if len(parts) < 2:
            return "-"

        buyer_section = parts[1]

        match = re.search(
            r"\b(?:VKN|TCKN)\s*:\s*(\d{10,11})",
            buyer_section,
            flags=re.IGNORECASE,
        )

        if not match:
            return "-"

        return match.group(1)