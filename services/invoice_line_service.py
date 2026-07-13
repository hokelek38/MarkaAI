import re
from decimal import Decimal, InvalidOperation


class InvoiceLineService:
    """
    E-fatura ve e-arşiv PDF metinlerinden mal/hizmet
    satırlarını çıkarmaya çalışan servis.

    Bu servis:
    - Açıklama
    - Miktar
    - Birim
    - Birim fiyat
    - KDV oranı
    - Satır matrahı

    alanlarını mümkün olduğu kadar ayrı ayrı döndürür.
    """

    SUMMARY_KEYWORDS = [
        "mal hizmet toplam",
        "mal/hizmet toplam",
        "toplam iskonto",
        "hesaplanan kdv",
        "toplam kdv",
        "vergiler dahil",
        "genel toplam",
        "ödenecek tutar",
        "toplam matrah",
        "kdv matrahı",
        "tevkifat",
        "yalnız",
    ]

    HEADER_KEYWORDS = [
        "mal hizmet",
        "mal / hizmet",
        "açıklama",
        "miktar",
        "birim fiyat",
        "kdv oranı",
        "kdv %",
        "tutar",
    ]

    UNIT_CODES = {
        "ADET",
        "AD",
        "C62",
        "KG",
        "KGM",
        "GR",
        "G",
        "M",
        "M2",
        "M²",
        "M3",
        "M³",
        "LT",
        "L",
        "PAKET",
        "PK",
        "KUTU",
        "KOLİ",
        "TON",
        "SAAT",
        "GÜN",
        "AY",
        "YIL",
        "HİZMET",
    }

    def parse(self, raw_text: str) -> list[dict]:
        """
        Ham PDF metninden fatura satırlarını çıkarır.
        """

        if not raw_text:
            return []

        normalized_lines = self._prepare_lines(
            raw_text
        )

        items = []

        for line_index, line in enumerate(
            normalized_lines,
            start=1,
        ):
            if not self._is_candidate_line(line):
                continue

            parsed_item = self._parse_line(
                line=line,
                line_index=line_index,
            )

            if parsed_item:
                items.append(parsed_item)

        return self._remove_duplicates(items)

    def _prepare_lines(
        self,
        raw_text: str,
    ) -> list[str]:
        """
        Metni temiz satırlara ayırır.
        """

        lines = []

        for raw_line in raw_text.splitlines():
            line = re.sub(
                r"\s+",
                " ",
                raw_line,
            ).strip()

            if not line:
                continue

            lines.append(line)

        return lines

    def _is_candidate_line(
        self,
        line: str,
    ) -> bool:
        """
        Satırın ürün veya hizmet satırı olma ihtimalini kontrol eder.
        """

        lowered = line.casefold()

        if any(
            keyword in lowered
            for keyword in self.SUMMARY_KEYWORDS
        ):
            return False

        if self._looks_like_header(lowered):
            return False

        amounts = self._find_amounts(line)

        if len(amounts) < 2:
            return False

        if not re.search(
            r"[A-Za-zÇĞİÖŞÜçğıöşü]",
            line,
        ):
            return False

        return True

    def _looks_like_header(
        self,
        lowered_line: str,
    ) -> bool:
        match_count = sum(
            1
            for keyword in self.HEADER_KEYWORDS
            if keyword in lowered_line
        )

        return match_count >= 3

    def _parse_line(
        self,
        *,
        line: str,
        line_index: int,
    ) -> dict | None:
        """
        Tek bir satırı alanlarına ayırır.
        """

        amounts = self._find_amounts(line)

        if len(amounts) < 2:
            return None

        amount_matches = list(
            self._amount_regex().finditer(line)
        )

        if len(amount_matches) < 2:
            return None

        line_total_match = amount_matches[-1]
        unit_price_match = amount_matches[-2]

        line_total_text = (
            line_total_match.group(0)
        )
        unit_price_text = (
            unit_price_match.group(0)
        )

        prefix = line[
            :unit_price_match.start()
        ].strip()

        vat_rate = self._find_vat_rate(line)

        quantity, unit, description = (
            self._extract_quantity_unit_description(
                prefix
            )
        )

        line_total = self._to_decimal(
            line_total_text
        )
        unit_price = self._to_decimal(
            unit_price_text
        )

        if line_total <= Decimal("0.00"):
            return None

        if not description:
            return None

        calculated_total = Decimal("0.00")

        if quantity > Decimal("0.00"):
            calculated_total = (
                quantity * unit_price
            ).quantize(
                Decimal("0.01")
            )

        difference = abs(
            calculated_total - line_total
        )

        calculation_matches = (
            quantity > Decimal("0.00")
            and difference <= Decimal("0.10")
        )

        return {
            "line_number": line_index,
            "description": description,
            "quantity": self._decimal_text(
                quantity
            ),
            "unit": unit,
            "unit_price": self._decimal_text(
                unit_price
            ),
            "vat_rate": vat_rate,
            "tax_base": self._decimal_text(
                line_total
            ),
            "line_total": self._decimal_text(
                line_total
            ),
            "calculated_total": (
                self._decimal_text(
                    calculated_total
                )
            ),
            "calculation_matches": (
                calculation_matches
            ),
            "raw_line": line,
        }

    def _extract_quantity_unit_description(
        self,
        prefix: str,
    ) -> tuple[Decimal, str, str]:
        """
        Satırın başlangıcından açıklama, miktar ve birimi çıkarır.
        """

        tokens = prefix.split()

        quantity = Decimal("0.00")
        unit = ""

        quantity_index = None

        for index in range(
            len(tokens) - 1,
            -1,
            -1,
        ):
            token = tokens[index]

            if self._looks_like_number(token):
                quantity_index = index
                quantity = self._to_decimal(
                    token
                )
                break

        if quantity_index is None:
            return (
                Decimal("0.00"),
                "",
                prefix,
            )

        if quantity_index + 1 < len(tokens):
            possible_unit = (
                tokens[quantity_index + 1]
                .upper()
                .replace(".", "")
            )

            if possible_unit in self.UNIT_CODES:
                unit = tokens[
                    quantity_index + 1
                ]

        description_tokens = tokens[
            :quantity_index
        ]

        if (
            description_tokens
            and description_tokens[0].isdigit()
        ):
            description_tokens = (
                description_tokens[1:]
            )

        description = " ".join(
            description_tokens
        ).strip(" -|")

        return quantity, unit, description

    def _find_vat_rate(
        self,
        line: str,
    ) -> int | None:
        """
        Satır içindeki KDV oranını bulur.
        """

        patterns = [
            r"%\s*(\d{1,2})",
            r"KDV\s*:?\s*(\d{1,2})",
            r"(\d{1,2})\s*%",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                line,
                flags=re.IGNORECASE,
            )

            if match:
                rate = int(match.group(1))

                if 0 <= rate <= 100:
                    return rate

        return None

    def _find_amounts(
        self,
        line: str,
    ) -> list[str]:
        return [
            match.group(0)
            for match in self._amount_regex().finditer(
                line
            )
        ]

    def _amount_regex(self):
        return re.compile(
            r"(?<![\w])"
            r"\d{1,3}(?:\.\d{3})*,\d{2}"
            r"|"
            r"(?<![\w])\d+,\d{2}"
            r"|"
            r"(?<![\w])\d+\.\d{2}"
        )

    def _looks_like_number(
        self,
        value: str,
    ) -> bool:
        cleaned = (
            value
            .replace("TL", "")
            .replace("₺", "")
            .strip()
        )

        return bool(
            re.fullmatch(
                r"\d+(?:[.,]\d+)?",
                cleaned,
            )
        )

    def _to_decimal(
        self,
        value,
    ) -> Decimal:
        normalized = (
            str(value)
            .replace("TL", "")
            .replace("₺", "")
            .replace(" ", "")
            .strip()
        )

        if not normalized:
            return Decimal("0.00")

        if "," in normalized:
            normalized = (
                normalized
                .replace(".", "")
                .replace(",", ".")
            )

        try:
            return Decimal(normalized)

        except InvalidOperation:
            return Decimal("0.00")

    def _decimal_text(
        self,
        value: Decimal,
    ) -> str:
        value = value.quantize(
            Decimal("0.01")
        )

        return format(value, ".2f")

    def _remove_duplicates(
        self,
        items: list[dict],
    ) -> list[dict]:
        """
        Aynı satırın PDF metninde birden fazla kez
        görünmesi ihtimaline karşı tekrarları kaldırır.
        """

        unique_items = []
        seen_keys = set()

        for item in items:
            key = (
                item.get(
                    "description",
                    "",
                ).casefold(),
                item.get(
                    "quantity",
                    "",
                ),
                item.get(
                    "unit_price",
                    "",
                ),
                item.get(
                    "line_total",
                    "",
                ),
            )

            if key in seen_keys:
                continue

            seen_keys.add(key)
            unique_items.append(item)

        for index, item in enumerate(
            unique_items,
            start=1,
        ):
            item["line_number"] = index

        return unique_items