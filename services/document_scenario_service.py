import re
import unicodedata
from decimal import Decimal, InvalidOperation


class DocumentScenarioService:
    """
    Fatura türünü ve vergi senaryosunu belirler.

    Desteklenen ilk senaryolar:
    - Standart alış faturası
    - Telefon / telekomünikasyon faturası
    - Faktoring faturası
    - Sıfır KDV / istisnalı fatura
    - Birden fazla KDV oranı içeren fatura

    Bu servis kesin muhasebe kaydı oluşturmaz.
    Belgeyi sınıflandırır ve muhasebe motoruna politika bilgisi verir.
    """

    RULE_SET_VERSION = "2026.07.1"

    TELECOM_KEYWORDS = [
        "telefon faturası",
        "mobil hizmet",
        "mobil iletişim",
        "elektronik haberleşme",
        "gsm",
        "internet hizmeti",
        "fiber internet",
        "sabit internet",
        "özel iletişim vergisi",
        "öiv",
        "turkcell",
        "vodafone",
        "türk telekom",
        "turktelekom",
        "superonline",
        "ttnet",
    ]

    FACTORING_KEYWORDS = [
        "faktoring",
        "factoring",
        "faktoring komisyonu",
        "faktoring faizi",
        "finansman komisyonu",
        "finansman faizi",
        "erken ödeme komisyonu",
        "iskonto faizi",
        "banka ve sigorta muameleleri vergisi",
        "bsmv",
    ]

    EXEMPTION_KEYWORDS = [
        "kdv istisnası",
        "kdv'den istisna",
        "kdv den istisna",
        "istisna kodu",
        "istisna sebebi",
        "muafiyet sebebi",
        "vergiden istisna",
        "17/4-e",
        "17/4",
    ]

    EXPORT_KEYWORDS = [
        "ihracat",
        "hizmet ihracı",
        "mal ihracı",
        "export",
        "gümrük beyannamesi",
        "ihraç kayıtlı",
    ]

    SPECIAL_COMMUNICATION_TAX_LABELS = [
        r"Özel\s*İletişim\s*Vergisi",
        r"ÖİV",
        r"OIV",
    ]

    BSMV_LABELS = [
        (
            r"Banka\s*ve\s*Sigorta\s*"
            r"Muameleleri\s*Vergisi"
        ),
        r"BSMV",
    ]

    FACTORING_COMMISSION_LABELS = [
        r"Faktoring\s*Komisyonu",
        r"Finansman\s*Komisyonu",
        r"İşlem\s*Komisyonu",
        r"Komisyon\s*Tutarı",
    ]

    FACTORING_INTEREST_LABELS = [
        r"Faktoring\s*Faizi",
        r"Finansman\s*Faizi",
        r"İskonto\s*Faizi",
        r"Faiz\s*Tutarı",
    ]

    def analyze(
        self,
        invoice_data: dict,
        company: dict | None = None,
    ) -> dict:
        """
        Faturayı sınıflandırır ve uygulanacak muhasebe
        politikasını hazırlar.
        """

        company = company or {}

        text = self._build_search_text(
            invoice_data
        )

        amounts = self._extract_amounts(
            invoice_data=invoice_data,
            text=text,
        )

        vat_rates = self._extract_vat_rates(
            invoice_data
        )

        detected_indicators = []

        telecom_matches = self._find_matches(
            text,
            self.TELECOM_KEYWORDS,
        )

        factoring_matches = self._find_matches(
            text,
            self.FACTORING_KEYWORDS,
        )

        exemption_matches = self._find_matches(
            text,
            self.EXEMPTION_KEYWORDS,
        )

        export_matches = self._find_matches(
            text,
            self.EXPORT_KEYWORDS,
        )

        detected_indicators.extend(
            telecom_matches
        )
        detected_indicators.extend(
            factoring_matches
        )
        detected_indicators.extend(
            exemption_matches
        )
        detected_indicators.extend(
            export_matches
        )

        has_zero_vat = self._has_zero_vat(
            invoice_data=invoice_data,
            text=text,
            amounts=amounts,
            vat_rates=vat_rates,
        )

        has_positive_vat = any(
            rate > Decimal("0")
            for rate in vat_rates
        )

        has_mixed_vat = (
            Decimal("0") in vat_rates
            and has_positive_vat
        )

        if has_mixed_vat:
            result = self._build_mixed_vat_result(
                invoice_data=invoice_data,
                amounts=amounts,
                vat_rates=vat_rates,
            )

        elif factoring_matches:
            result = self._build_factoring_result(
                invoice_data=invoice_data,
                company=company,
                amounts=amounts,
                vat_rates=vat_rates,
                matches=factoring_matches,
            )

        elif telecom_matches:
            result = self._build_telecom_result(
                invoice_data=invoice_data,
                company=company,
                amounts=amounts,
                vat_rates=vat_rates,
                matches=telecom_matches,
            )

        elif has_zero_vat:
            result = self._build_zero_vat_result(
                invoice_data=invoice_data,
                amounts=amounts,
                vat_rates=vat_rates,
                exemption_matches=exemption_matches,
                export_matches=export_matches,
                text=text,
            )

        else:
            result = self._build_standard_result(
                invoice_data=invoice_data,
                amounts=amounts,
                vat_rates=vat_rates,
            )

        result["rule_set_version"] = (
            self.RULE_SET_VERSION
        )

        result["detected_indicators"] = list(
            dict.fromkeys(
                detected_indicators
            )
        )

        result["amounts"] = {
            key: self._decimal_text(value)
            for key, value in amounts.items()
        }

        result["vat_rates"] = [
            self._decimal_text(rate)
            for rate in vat_rates
        ]

        result["requires_accountant_approval"] = True

        return result

    def _build_telecom_result(
        self,
        *,
        invoice_data: dict,
        company: dict,
        amounts: dict,
        vat_rates: list[Decimal],
        matches: list[str],
    ) -> dict:
        """
        Telefon ve internet faturası politikası.
        """

        policy = company.get(
            "accounting_policy",
            {},
        )

        telecom_account = str(
            policy.get(
                "telecom_expense_account",
                "770",
            )
        )

        non_deductible_tax_account = str(
            policy.get(
                "non_deductible_tax_account",
                "689",
            )
        )

        warnings = [
            (
                "Telefon veya internet giderinin "
                "üretim, satış ya da genel yönetim "
                "amacı kullanıcı tarafından doğrulanmalıdır."
            ),
            (
                "Özel İletişim Vergisi ayrı muhasebe "
                "satırında ve KKEG niteliğiyle izlenmelidir."
            ),
        ]

        blocking_errors = []

        text = self._build_search_text(
            invoice_data
        )

        oiv_is_mentioned = self._contains_any(
            text,
            [
                "özel iletişim vergisi",
                "öiv",
                "oiv",
            ],
        )

        if (
            oiv_is_mentioned
            and amounts["special_communication_tax"]
            <= Decimal("0.00")
        ):
            blocking_errors.append(
                "ÖİV ifadesi bulundu ancak ÖİV tutarı okunamadı."
            )

        if (
            amounts["vat_amount"]
            <= Decimal("0.00")
            and amounts["tax_base"]
            > Decimal("0.00")
        ):
            warnings.append(
                (
                    "Telefon faturasında KDV tutarı sıfır "
                    "veya okunamamış görünüyor. Vergi "
                    "senaryosu kontrol edilmelidir."
                )
            )

        return {
            "scenario_code": "TELECOM_INVOICE",
            "document_category": "telecom",
            "tax_scenario": "telecom_with_oiv",
            "confidence": self._confidence_from_matches(
                matches,
                base=78,
            ),
            "base_account_candidate": telecom_account,
            "vat_account_candidate": (
                "191"
                if amounts["vat_amount"]
                > Decimal("0.00")
                else None
            ),
            "special_tax_account_candidate": (
                non_deductible_tax_account
            ),
            "special_tax_type": "OIV",
            "special_tax_is_non_deductible": True,
            "requires_usage_confirmation": True,
            "requires_counter_account_confirmation": False,
            "warnings": warnings,
            "blocking_errors": blocking_errors,
            "posting_policy": {
                "service_base": (
                    "Faaliyetteki kullanım amacına göre "
                    "730, 760 veya 770"
                ),
                "deductible_vat": "191",
                "special_communication_tax": (
                    non_deductible_tax_account
                ),
                "special_communication_tax_kkeq": True,
                "supplier": "320",
            },
        }

    def _build_factoring_result(
        self,
        *,
        invoice_data: dict,
        company: dict,
        amounts: dict,
        vat_rates: list[Decimal],
        matches: list[str],
    ) -> dict:
        """
        Faktoring faturası politikası.
        """

        policy = company.get(
            "accounting_policy",
            {},
        )

        finance_expense_account = str(
            policy.get(
                "finance_expense_account",
                "780",
            )
        )

        warnings = [
            (
                "Faktoring anapara veya avans tutarı "
                "finansman gideri değildir; yalnızca faiz, "
                "komisyon ve ilgili vergi/giderler ayrıştırılmalıdır."
            ),
            (
                "Karşı hesap; işlem yapısına göre banka, "
                "faktoring borcu, satıcı veya diğer finansal "
                "borç hesabı olabilir."
            ),
        ]

        blocking_errors = []

        if amounts["vat_amount"] > Decimal("0.00"):
            blocking_errors.append(
                (
                    "Faktoring veya BSMV göstergesi bulunan "
                    "belgede KDV tutarı da bulundu. Belge karma "
                    "işlem içerebilir ve manuel kontrol gerektirir."
                )
            )

        if (
            self._contains_any(
                self._build_search_text(
                    invoice_data
                ),
                [
                    "bsmv",
                    (
                        "banka ve sigorta "
                        "muameleleri vergisi"
                    ),
                ],
            )
            and amounts["bsmv_amount"]
            <= Decimal("0.00")
        ):
            warnings.append(
                "BSMV ifadesi bulundu ancak tutarı okunamadı."
            )

        return {
            "scenario_code": "FACTORING_INVOICE",
            "document_category": "factoring",
            "tax_scenario": "bsmv_exempt_from_vat",
            "confidence": self._confidence_from_matches(
                matches,
                base=82,
            ),
            "base_account_candidate": (
                finance_expense_account
            ),
            "vat_account_candidate": None,
            "special_tax_account_candidate": (
                finance_expense_account
            ),
            "special_tax_type": "BSMV",
            "special_tax_is_non_deductible": False,
            "requires_usage_confirmation": False,
            "requires_counter_account_confirmation": True,
            "warnings": warnings,
            "blocking_errors": blocking_errors,
            "posting_policy": {
                "factoring_interest": (
                    finance_expense_account
                ),
                "factoring_commission": (
                    finance_expense_account
                ),
                "bsmv": finance_expense_account,
                "deductible_vat": None,
                "principal_or_advance": (
                    "Gider hesabına kaydedilmez"
                ),
                "counter_account": (
                    "İşleme göre kullanıcı tarafından seçilir"
                ),
            },
        }

    def _build_zero_vat_result(
        self,
        *,
        invoice_data: dict,
        amounts: dict,
        vat_rates: list[Decimal],
        exemption_matches: list[str],
        export_matches: list[str],
        text: str,
    ) -> dict:
        """
        KDV tutarı sıfır olan faturaların politikası.
        """

        exemption_code = (
            self._extract_exemption_code(
                invoice_data=invoice_data,
                text=text,
            )
        )

        exemption_reason = (
            self._extract_exemption_reason(
                invoice_data=invoice_data,
                text=text,
            )
        )

        warnings = [
            (
                "Sıfır KDV, otomatik olarak standart "
                "bir KDV oranı kabul edilmemelidir."
            ),
            (
                "Matrah ilgili mal veya hizmetin kullanım "
                "amacına göre gider, stok veya duran varlık "
                "hesabına yönlendirilmelidir."
            ),
        ]

        blocking_errors = []

        if export_matches:
            tax_scenario = "export_or_export_related"
            scenario_code = "ZERO_VAT_EXPORT"

        elif exemption_matches:
            tax_scenario = "vat_exemption"
            scenario_code = "ZERO_VAT_EXEMPT"

        else:
            tax_scenario = "zero_vat_unresolved"
            scenario_code = "ZERO_VAT_UNKNOWN"

        if (
            not exemption_code
            and not exemption_reason
            and not export_matches
        ):
            blocking_errors.append(
                (
                    "KDV sıfır olmasına rağmen istisna "
                    "kodu veya istisna sebebi okunamadı."
                )
            )

        return {
            "scenario_code": scenario_code,
            "document_category": "zero_vat",
            "tax_scenario": tax_scenario,
            "confidence": (
                85
                if exemption_code
                else 70
                if exemption_reason
                else 35
            ),
            "base_account_candidate": None,
            "vat_account_candidate": None,
            "special_tax_account_candidate": None,
            "special_tax_type": None,
            "special_tax_is_non_deductible": False,
            "exemption_code": exemption_code,
            "exemption_reason": exemption_reason,
            "requires_usage_confirmation": True,
            "requires_counter_account_confirmation": False,
            "warnings": warnings,
            "blocking_errors": blocking_errors,
            "posting_policy": {
                "base_amount": (
                    "Kalemin kullanım amacına göre hesap seçilir"
                ),
                "deductible_vat": None,
                "supplier": "320",
                "automatic_approval": False,
            },
        }

    def _build_mixed_vat_result(
        self,
        *,
        invoice_data: dict,
        amounts: dict,
        vat_rates: list[Decimal],
    ) -> dict:
        """
        Aynı faturada sıfır ve pozitif KDV oranları varsa
        bütün faturaya tek vergi senaryosu uygulanmasını engeller.
        """

        return {
            "scenario_code": "MIXED_VAT_INVOICE",
            "document_category": "mixed_vat",
            "tax_scenario": "line_level_vat_required",
            "confidence": 90,
            "base_account_candidate": None,
            "vat_account_candidate": "191",
            "special_tax_account_candidate": None,
            "special_tax_type": None,
            "special_tax_is_non_deductible": False,
            "requires_usage_confirmation": True,
            "requires_counter_account_confirmation": False,
            "warnings": [
                (
                    "Faturada sıfır ve pozitif KDV oranlı "
                    "kalemler birlikte bulundu."
                ),
                (
                    "KDV ve matrah hesaplaması fatura toplamı "
                    "yerine kalem bazında yapılmalıdır."
                ),
            ],
            "blocking_errors": [],
            "posting_policy": {
                "base_amount": (
                    "Her kalem ayrı hesap ve vergi "
                    "senaryosuyla işlenir"
                ),
                "deductible_vat": (
                    "Yalnızca pozitif KDV tutarlı ve "
                    "indirilebilir kalemler için 191"
                ),
                "supplier": "320",
            },
        }

    def _build_standard_result(
        self,
        *,
        invoice_data: dict,
        amounts: dict,
        vat_rates: list[Decimal],
    ) -> dict:
        return {
            "scenario_code": "STANDARD_INVOICE",
            "document_category": "standard",
            "tax_scenario": "standard_vat",
            "confidence": 70,
            "base_account_candidate": None,
            "vat_account_candidate": (
                "191"
                if amounts["vat_amount"]
                > Decimal("0.00")
                else None
            ),
            "special_tax_account_candidate": None,
            "special_tax_type": None,
            "special_tax_is_non_deductible": False,
            "requires_usage_confirmation": True,
            "requires_counter_account_confirmation": False,
            "warnings": [],
            "blocking_errors": [],
            "posting_policy": {
                "base_amount": (
                    "Kalemin kullanım amacına göre hesap seçilir"
                ),
                "deductible_vat": "191",
                "supplier": "320",
            },
        }

    def _extract_amounts(
        self,
        *,
        invoice_data: dict,
        text: str,
    ) -> dict:
        return {
            "tax_base": self._first_positive_amount(
                invoice_data,
                [
                    "tax_base_amount",
                    "accounting_base_amount",
                    "subtotal",
                ],
            ),
            "vat_amount": self._amount_to_decimal(
                invoice_data.get(
                    "vat_amount",
                    "0",
                )
            ),
            "total_amount": (
                self._first_positive_or_labeled_amount(
                    data=invoice_data,
                    keys=[
                        "total_amount",
                    ],
                    text=text,
                    label_patterns=[
                        (
                            r"Vergiler\\s*Dahil\\s*"
                            r"Toplam\\s*Tutar"
                        ),
                        r"Genel\\s*Toplam",
                    ],
                )
            ),
            "payable_amount": (
                self._first_positive_or_labeled_amount(
                    data=invoice_data,
                    keys=[
                        "payable_amount",
                    ],
                    text=text,
                    label_patterns=[
                        r"Ödenecek\\s*Tutar",
                        r"Ödenecek\\s*Toplam",
                    ],
                )
            ),
            "special_communication_tax": (
                self._find_first_labeled_amount(
                    text,
                    self.SPECIAL_COMMUNICATION_TAX_LABELS,
                )
            ),
            "bsmv_amount": (
                self._find_first_labeled_amount(
                    text,
                    self.BSMV_LABELS,
                )
            ),
            "factoring_commission": (
                self._find_first_labeled_amount(
                    text,
                    self.FACTORING_COMMISSION_LABELS,
                )
            ),
            "factoring_interest": (
                self._find_first_labeled_amount(
                    text,
                    self.FACTORING_INTEREST_LABELS,
                )
            ),
        }

    def _first_positive_or_labeled_amount(
        self,
        *,
        data: dict,
        keys: list[str],
        text: str,
        label_patterns: list[str],
    ) -> Decimal:
        """
        Önce yapılandırılmış alana, ardından ham metne bakar.
        """

        direct_amount = self._first_positive_amount(
            data,
            keys,
        )

        if direct_amount > Decimal("0.00"):
            return direct_amount

        return self._find_first_labeled_amount(
            text,
            label_patterns,
        )

    def _extract_vat_rates(
        self,
        invoice_data: dict,
    ) -> list[Decimal]:
        rates = set()

        for item in invoice_data.get(
            "line_items",
            [],
        ):
            rate = item.get(
                "vat_rate"
            )

            if rate is None:
                continue

            decimal_rate = self._amount_to_decimal(
                rate
            )

            if (
                Decimal("0")
                <= decimal_rate
                <= Decimal("100")
            ):
                rates.add(decimal_rate)

        raw_text = str(
            invoice_data.get(
                "raw_text",
                "",
            )
        )

        patterns = [
            r"KDV\s*(?:Oranı)?\s*:?\s*%\s*(\d{1,2})",
            r"%\s*(\d{1,2})\s*KDV",
            r"KDV\s*(\d{1,2})\s*%",
        ]

        for pattern in patterns:
            for match in re.finditer(
                pattern,
                raw_text,
                flags=re.IGNORECASE,
            ):
                rates.add(
                    Decimal(
                        match.group(1)
                    )
                )

        return sorted(rates)

    def _has_zero_vat(
        self,
        *,
        invoice_data: dict,
        text: str,
        amounts: dict,
        vat_rates: list[Decimal],
    ) -> bool:
        if Decimal("0") in vat_rates:
            return True

        if re.search(
            r"(?:KDV|K\.D\.V\.)\s*:?\s*%?\s*0(?:[,\.]00)?",
            text,
            flags=re.IGNORECASE,
        ):
            return True

        return (
            amounts["tax_base"]
            > Decimal("0.00")
            and amounts["vat_amount"]
            == Decimal("0.00")
        )

    def _extract_exemption_code(
        self,
        *,
        invoice_data: dict,
        text: str,
    ) -> str:
        direct_value = str(
            invoice_data.get(
                "tax_exemption_reason_code",
                invoice_data.get(
                    "exemption_code",
                    "",
                ),
            )
            or ""
        ).strip()

        if direct_value:
            return direct_value

        patterns = [
            (
                r"(?:İstisna|Muafiyet)\s*Kodu"
                r"\s*:?\s*([A-Z0-9.-]+)"
            ),
            (
                r"TaxExemptionReasonCode"
                r"\s*:?\s*([A-Z0-9.-]+)"
            ),
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:
                return match.group(1).strip()

        return ""

    def _extract_exemption_reason(
        self,
        *,
        invoice_data: dict,
        text: str,
    ) -> str:
        direct_value = str(
            invoice_data.get(
                "tax_exemption_reason",
                invoice_data.get(
                    "exemption_reason",
                    "",
                ),
            )
            or ""
        ).strip()

        if direct_value:
            return direct_value

        patterns = [
            (
                r"(?:İstisna|Muafiyet)\s*Sebebi"
                r"\s*:?\s*([^\n\r]+)"
            ),
            (
                r"TaxExemptionReason"
                r"\s*:?\s*([^\n\r]+)"
            ),
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:
                return match.group(1).strip()

        return ""

    def _find_first_labeled_amount(
        self,
        text: str,
        label_patterns: list[str],
    ) -> Decimal:
        amount_pattern = (
            r"("
            r"\d{1,3}(?:\.\d{3})*,\d{2}"
            r"|"
            r"\d+,\d{2}"
            r"|"
            r"\d+\.\d{2}"
            r")"
        )

        for label_pattern in label_patterns:
            pattern = (
                rf"{label_pattern}\s*:?\s*"
                rf"(?:\n+\s*)?"
                rf"{amount_pattern}\s*(?:TL|₺)?"
            )

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:
                return self._amount_to_decimal(
                    match.group(1)
                )

        return Decimal("0.00")

    def _first_positive_amount(
        self,
        data: dict,
        keys: list[str],
    ) -> Decimal:
        for key in keys:
            amount = self._amount_to_decimal(
                data.get(
                    key,
                    "0",
                )
            )

            if amount > Decimal("0.00"):
                return amount

        return Decimal("0.00")

    def _build_search_text(
        self,
        invoice_data: dict,
    ) -> str:
        """
        Vergi başlıklarının özgün Türkçe karakterlerini korur.
        """

        parts = [
            invoice_data.get(
                "raw_text",
                "",
            ),
            invoice_data.get(
                "seller_name",
                "",
            ),
            invoice_data.get(
                "buyer_name",
                "",
            ),
            invoice_data.get(
                "invoice_type",
                "",
            ),
            invoice_data.get(
                "scenario",
                "",
            ),
        ]

        return "\n".join(
            str(part)
            for part in parts
            if part
        )

    def _normalize_for_search(
        self,
        value: str,
    ) -> str:
        """
        Anahtar kelime aramasında Türkçe büyük İ gibi
        karakterlerden kaynaklanan eşleşme sorunlarını giderir.
        """

        normalized = unicodedata.normalize(
            "NFKD",
            str(value),
        )

        normalized = "".join(
            character
            for character in normalized
            if not unicodedata.combining(
                character
            )
        )

        return normalized.casefold()

    def _find_matches(
        self,
        text: str,
        keywords: list[str],
    ) -> list[str]:
        normalized_text = (
            self._normalize_for_search(text)
        )

        return [
            keyword
            for keyword in keywords
            if self._normalize_for_search(
                keyword
            ) in normalized_text
        ]

    def _contains_any(
        self,
        text: str,
        keywords: list[str],
    ) -> bool:
        normalized_text = (
            self._normalize_for_search(text)
        )

        return any(
            self._normalize_for_search(
                keyword
            ) in normalized_text
            for keyword in keywords
        )

    def _confidence_from_matches(
        self,
        matches: list[str],
        *,
        base: int,
    ) -> int:
        return min(
            98,
            base + max(
                0,
                len(matches) - 1
            ) * 4,
        )

    def _amount_to_decimal(
        self,
        value,
    ) -> Decimal:
        normalized = (
            str(value)
            .replace("TL", "")
            .replace("₺", "")
            .replace("%", "")
            .replace(" ", "")
            .strip()
        )

        if normalized in {
            "",
            "-",
            "None",
        }:
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
        return format(
            value.quantize(
                Decimal("0.01")
            ),
            ".2f",
        )
