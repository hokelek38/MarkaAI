import re
from decimal import Decimal, InvalidOperation


class TelecomInvoiceService:
    """
    TTNET / Türk Telekom internet ve telefon faturalarını ayrıştırır.

    Ayrı okunan alanlar:
    - KDV matrahı
    - KDV oranı ve tutarı
    - ÖİV matrahı, oranı ve tutarı
    - Toplam vergiler
    - Önceki ve gelecek dönem devirleri
    - Cari dönem ödenecek toplam
    """

    def analyze(
        self,
        invoice_data: dict | None = None,
        raw_text: str = "",
    ) -> dict:
        invoice_data = invoice_data or {}

        text = raw_text or str(
            invoice_data.get(
                "raw_text",
                "",
            )
        )

        if not text.strip():
            raise ValueError(
                "Telekom faturası metni boş olamaz."
            )

        vat = self._tax_block(
            text,
            [
                r"KDV",
            ],
        )

        oiv = self._tax_block(
            text,
            [
                r"ÖİV",
                r"OİV",
                r"OIV",
                r"Özel\s*İletişim\s*Vergisi",
            ],
        )

        payable_total = self._amount(
            text,
            [
                r"ÖDENECEK\s*TOPLAM",
                r"ÖDENECEK\s*TUTAR",
            ],
        )

        total_invoice_amount = self._amount(
            text,
            [
                r"TOPLAM\s*FATURA\s*TUTARI",
            ],
        )

        total_taxes = self._amount(
            text,
            [
                (
                    r"DEVLETE\s*ÖDENEN\s*"
                    r"VERGİLER\s*TOPLAMI"
                ),
            ],
        )

        previous_carry = self._amount(
            text,
            [
                r"Önceki\s*Aydan\s*Devir",
            ],
        )

        next_carry = self._amount(
            text,
            [
                r"Gelecek\s*Aya\s*Devir",
            ],
        )

        service_expense_base = vat["base"]

        if service_expense_base <= Decimal("0.00"):
            service_expense_base = (
                self._first_positive(
                    invoice_data,
                    [
                        "tax_base_amount",
                        "accounting_base_amount",
                        "subtotal",
                    ],
                )
            )

        if payable_total <= Decimal("0.00"):
            payable_total = (
                self._first_positive(
                    invoice_data,
                    [
                        "payable_amount",
                        "total_amount",
                    ],
                )
            )

        calculated_tax_total = (
            vat["amount"]
            + oiv["amount"]
        ).quantize(
            Decimal("0.01")
        )

        calculated_payable = (
            service_expense_base
            + vat["amount"]
            + oiv["amount"]
        ).quantize(
            Decimal("0.01")
        )

        carry_net = (
            previous_carry
            + next_carry
        ).quantize(
            Decimal("0.01")
        )

        validations = {
            "tax_total_matches": self._equal(
                calculated_tax_total,
                total_taxes,
            ),
            "base_tax_payable_matches": (
                self._equal(
                    calculated_payable,
                    payable_total,
                )
            ),
            "invoice_total_matches_payable": (
                self._equal(
                    total_invoice_amount,
                    payable_total,
                )
            ),
            "carry_net_is_zero": self._equal(
                carry_net,
                Decimal("0.00"),
            ),
        }

        warnings = []

        if not validations[
            "tax_total_matches"
        ]:
            warnings.append(
                "KDV ve ÖİV toplamı, faturadaki "
                "vergi toplamıyla eşleşmiyor."
            )

        if not validations[
            "base_tax_payable_matches"
        ]:
            warnings.append(
                "KDV matrahı + KDV + ÖİV, "
                "ödenecek tutarla eşleşmiyor."
            )

        if not validations[
            "invoice_total_matches_payable"
        ]:
            warnings.append(
                "Toplam fatura tutarı ile "
                "ödenecek toplam eşleşmiyor."
            )

        if not validations[
            "carry_net_is_zero"
        ]:
            warnings.append(
                "Önceki ve gelecek dönem "
                "devirleri net sıfır değil."
            )

        blocking_errors = []

        if service_expense_base <= Decimal("0.00"):
            blocking_errors.append(
                "KDV matrahı okunamadı."
            )

        if payable_total <= Decimal("0.00"):
            blocking_errors.append(
                "Ödenecek toplam okunamadı."
            )

        if not validations[
            "base_tax_payable_matches"
        ]:
            blocking_errors.append(
                "Telekom faturası muhasebe "
                "toplamı doğrulanamadı."
            )

        return {
            "recognized": self._recognized(
                text
            ),
            "scenario_code": (
                "TELECOM_INVOICE"
            ),
            "provider_name": self._provider(
                text
            ),
            "provider_tax_number": (
                self._value(
                    text,
                    [
                        r"Vergi\s*Numarası",
                        r"VKN",
                    ],
                )
            ),
            "invoice_id": self._value(
                text,
                [
                    r"Fatura\s*ID",
                ],
            ),
            "invoice_number": self._value(
                text,
                [
                    r"FATURA\s*NO",
                    r"Fatura\s*No",
                ],
            ),
            "invoice_date": self._date(
                text,
                [
                    r"Fatura\s*Tarih(?:i)?",
                ],
            ),
            "service_number": self._value(
                text,
                [
                    r"HİZMET\s*NO",
                ],
            ),
            "service_type": self._value(
                text,
                [
                    r"HİZMET\s*TÜRÜ",
                ],
            ),
            "billing_period": self._value(
                text,
                [
                    r"DÖNEM",
                ],
            ),
            "due_date": self._date(
                text,
                [
                    r"SON\s*ÖDEME\s*TARİHİ",
                ],
            ),
            "account_number": self._value(
                text,
                [
                    r"HESAP\s*NUMARASI",
                ],
            ),
            "amounts": {
                "service_expense_base": (
                    self._text(
                        service_expense_base
                    )
                ),
                "vat_rate": self._text(
                    vat["rate"]
                ),
                "vat_base": self._text(
                    vat["base"]
                ),
                "vat_amount": self._text(
                    vat["amount"]
                ),
                "oiv_rate": self._text(
                    oiv["rate"]
                ),
                "oiv_base": self._text(
                    oiv["base"]
                ),
                "oiv_amount": self._text(
                    oiv["amount"]
                ),
                "total_taxes": self._text(
                    total_taxes
                ),
                "total_invoice_amount": (
                    self._text(
                        total_invoice_amount
                    )
                ),
                "previous_carry": self._text(
                    previous_carry
                ),
                "next_carry": self._text(
                    next_carry
                ),
                "carry_net": self._text(
                    carry_net
                ),
                "payable_total": self._text(
                    payable_total
                ),
                "calculated_payable": (
                    self._text(
                        calculated_payable
                    )
                ),
            },
            "accounting_components": {
                "expense_base": self._text(
                    service_expense_base
                ),
                "deductible_vat": self._text(
                    vat["amount"]
                ),
                "special_communication_tax": (
                    self._text(
                        oiv["amount"]
                    )
                ),
                "supplier_credit": self._text(
                    payable_total
                ),
                "expense_account_code": None,
                "oiv_account_code": None,
                "vat_account_code": "191",
                "supplier_account_code": "320",
            },
            "validations": validations,
            "warnings": warnings,
            "blocking_errors": (
                blocking_errors
            ),
            "posting_blocked": bool(
                blocking_errors
            ),
            "requires_company_policy": True,
        }

    def _tax_block(
        self,
        text: str,
        labels: list[str],
    ) -> dict:
        label_group = "|".join(
            f"(?:{label})"
            for label in labels
        )

        pattern = (
            rf"(?:{label_group})\s*%\s*"
            rf"(\d{{1,2}}(?:[.,]\d+)?)\s*"
            rf"\(\s*Matrah\s*"
            rf"([+-]?\d[\d.,]*)\s*\)\s*"
            rf"([+-]?\d[\d.,]*)"
        )

        match = re.search(
            pattern,
            text,
            flags=(
                re.IGNORECASE
                | re.DOTALL
            ),
        )

        if not match:
            return {
                "rate": Decimal("0.00"),
                "base": Decimal("0.00"),
                "amount": Decimal("0.00"),
            }

        return {
            "rate": self._decimal(
                match.group(1)
            ),
            "base": self._decimal(
                match.group(2)
            ),
            "amount": self._decimal(
                match.group(3)
            ),
        }

    def _amount(
        self,
        text: str,
        labels: list[str],
    ) -> Decimal:
        amount_pattern = (
            r"([+-]?"
            r"(?:"
            r"\d{1,3}(?:\.\d{3})*,\d{2}"
            r"|"
            r"\d+,\d{2}"
            r"|"
            r"\d+\.\d{2}"
            r")"
            r")"
        )

        for label in labels:
            match = re.search(
                (
                    rf"{label}\s*:?\s*"
                    rf"(?:\n+\s*)?"
                    rf"{amount_pattern}"
                    rf"\s*(?:TL|₺)?"
                ),
                text,
                flags=re.IGNORECASE,
            )

            if match:
                return self._decimal(
                    match.group(1)
                )

        return Decimal("0.00")

    def _value(
        self,
        text: str,
        labels: list[str],
    ) -> str:
        for label in labels:
            match = re.search(
                (
                    rf"{label}\s*:?\s*"
                    rf"(?:\n+\s*)?"
                    rf"([^\n\r]+)"
                ),
                text,
                flags=re.IGNORECASE,
            )

            if match:
                return re.sub(
                    r"\s+",
                    " ",
                    match.group(1),
                ).strip(" :")

        return ""

    def _date(
        self,
        text: str,
        labels: list[str],
    ) -> str:
        date_pattern = (
            r"(\d{2}[./-]\d{2}[./-]\d{4}"
            r"(?:\s+\d{2}:\d{2})?)"
        )

        for label in labels:
            match = re.search(
                (
                    rf"{label}\s*:?\s*"
                    rf"(?:\n+\s*)?"
                    rf"{date_pattern}"
                ),
                text,
                flags=re.IGNORECASE,
            )

            if match:
                return match.group(1)

        return ""

    def _provider(
        self,
        text: str,
    ) -> str:
        if re.search(
            (
                r"TTNET\s+ANON[İI]M\s+"
                r"[ŞS][İI]RKET[İI]"
            ),
            text,
            flags=re.IGNORECASE,
        ):
            return (
                "TTNET ANONİM ŞİRKETİ"
            )

        if re.search(
            r"TÜRK\s*TELEKOM",
            text,
            flags=re.IGNORECASE,
        ):
            return "TÜRK TELEKOM"

        return ""

    def _recognized(
        self,
        text: str,
    ) -> bool:
        return bool(
            re.search(
                (
                    r"TTNET"
                    r"|TÜRK\s*TELEKOM"
                    r"|ÖİV\s*%"
                ),
                text,
                flags=re.IGNORECASE,
            )
        )

    def _first_positive(
        self,
        data: dict,
        keys: list[str],
    ) -> Decimal:
        for key in keys:
            amount = self._decimal(
                data.get(
                    key,
                    "0",
                )
            )

            if amount > Decimal("0.00"):
                return amount

        return Decimal("0.00")

    def _decimal(
        self,
        value,
    ) -> Decimal:
        normalized = (
            str(value)
            .replace("TL", "")
            .replace("₺", "")
            .replace("%", "")
            .replace("\u00a0", "")
            .replace(" ", "")
            .strip()
        )

        if normalized in {
            "",
            "-",
            "None",
        }:
            return Decimal("0.00")

        if (
            "," in normalized
            and "." in normalized
        ):
            normalized = (
                normalized
                .replace(".", "")
                .replace(",", ".")
            )

        elif "," in normalized:
            normalized = (
                normalized.replace(
                    ",",
                    ".",
                )
            )

        try:
            return Decimal(normalized)

        except InvalidOperation:
            return Decimal("0.00")

    def _text(
        self,
        value: Decimal,
    ) -> str:
        return format(
            value.quantize(
                Decimal("0.01")
            ),
            ".2f",
        )

    def _equal(
        self,
        left: Decimal,
        right: Decimal,
    ) -> bool:
        return (
            abs(left - right)
            <= Decimal("0.02")
        )
