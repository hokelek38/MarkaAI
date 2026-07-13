import re
import unicodedata
from pathlib import Path


class DocumentRegistryService:
    """
    Muhasebeye konu olabilecek belgeleri tanır ve sınıflandırır.

    Bu servis:
    - Belgenin hukuki/teknik türünü belirler.
    - Belgenin muhasebe kaydı oluşturup oluşturamayacağını bildirir.
    - Özel okuyucu gerektiren belgeleri yönlendirir.
    - Zorunlu alan eksiklerini tespit eder.

    Muhasebe hesabı seçmez.
    """

    REGISTRY_VERSION = "2026.07.1"

    DOCUMENT_DEFINITIONS = {
        "INVOICE": {
            "display_name": "Fatura",
            "family": "invoice",
            "accounting_effect": "direct",
            "posting_allowed": True,
            "special_processor": "",
            "requires_company_classification": True,
            "requires_tax_analysis": True,
            "required_fields": [
                "invoice_number",
                "invoice_date",
                "seller_tax_number",
                "payable_amount",
            ],
        },
        "TELECOM_INVOICE": {
            "display_name": "Telefon / İnternet Faturası",
            "family": "invoice",
            "accounting_effect": "direct",
            "posting_allowed": True,
            "special_processor": "telecom_invoice_service",
            "requires_company_classification": True,
            "requires_tax_analysis": True,
            "required_fields": [
                "invoice_number",
                "invoice_date",
                "seller_tax_number",
                "tax_base_amount",
                "vat_amount",
                "oiv_amount",
                "payable_amount",
            ],
        },
        "FACTORING_DOCUMENT": {
            "display_name": "Faktoring Belgesi / Faturası",
            "family": "financial_document",
            "accounting_effect": "conditional",
            "posting_allowed": True,
            "special_processor": "factoring_invoice_service",
            "requires_company_classification": False,
            "requires_tax_analysis": True,
            "required_fields": [
                "invoice_number",
                "invoice_date",
                "payable_amount",
            ],
        },
        "SELF_EMPLOYMENT_RECEIPT": {
            "display_name": "Serbest Meslek Makbuzu",
            "family": "invoice_substitute",
            "accounting_effect": "direct",
            "posting_allowed": True,
            "special_processor": "self_employment_receipt_service",
            "requires_company_classification": True,
            "requires_tax_analysis": True,
            "required_fields": [
                "document_number",
                "document_date",
                "seller_tax_number",
                "payable_amount",
            ],
        },
        "EXPENSE_VOUCHER": {
            "display_name": "Gider Pusulası",
            "family": "invoice_substitute",
            "accounting_effect": "direct",
            "posting_allowed": True,
            "special_processor": "expense_voucher_service",
            "requires_company_classification": True,
            "requires_tax_analysis": True,
            "required_fields": [
                "document_number",
                "document_date",
                "payable_amount",
            ],
        },
        "PRODUCER_RECEIPT": {
            "display_name": "Müstahsil Makbuzu",
            "family": "invoice_substitute",
            "accounting_effect": "direct",
            "posting_allowed": True,
            "special_processor": "producer_receipt_service",
            "requires_company_classification": True,
            "requires_tax_analysis": True,
            "required_fields": [
                "document_number",
                "document_date",
                "payable_amount",
            ],
        },
        "RETAIL_RECEIPT": {
            "display_name": "Perakende Satış / ÖKC Fişi",
            "family": "invoice_substitute",
            "accounting_effect": "conditional",
            "posting_allowed": True,
            "special_processor": "retail_receipt_service",
            "requires_company_classification": True,
            "requires_tax_analysis": True,
            "required_fields": [
                "document_date",
                "payable_amount",
            ],
        },
        "PASSENGER_TICKET": {
            "display_name": "Yolcu Taşıma Bileti",
            "family": "invoice_substitute",
            "accounting_effect": "conditional",
            "posting_allowed": True,
            "special_processor": "ticket_service",
            "requires_company_classification": True,
            "requires_tax_analysis": True,
            "required_fields": [
                "document_date",
                "payable_amount",
            ],
        },
        "BANK_RECEIPT": {
            "display_name": "Banka Dekontu",
            "family": "financial_document",
            "accounting_effect": "direct",
            "posting_allowed": True,
            "special_processor": "bank_receipt_service",
            "requires_company_classification": False,
            "requires_tax_analysis": False,
            "required_fields": [
                "document_date",
                "payable_amount",
            ],
        },
        "INSURANCE_POLICY": {
            "display_name": "Sigorta Poliçesi",
            "family": "financial_document",
            "accounting_effect": "conditional",
            "posting_allowed": True,
            "special_processor": "insurance_policy_service",
            "requires_company_classification": True,
            "requires_tax_analysis": True,
            "required_fields": [
                "document_number",
                "document_date",
                "payable_amount",
            ],
        },
        "PAYROLL": {
            "display_name": "Ücret Bordrosu",
            "family": "payroll",
            "accounting_effect": "direct",
            "posting_allowed": True,
            "special_processor": "payroll_service",
            "requires_company_classification": False,
            "requires_tax_analysis": True,
            "required_fields": [
                "document_date",
                "payable_amount",
            ],
        },
        "DISPATCH_NOTE": {
            "display_name": "Sevk / Taşıma İrsaliyesi",
            "family": "movement_document",
            "accounting_effect": "none",
            "posting_allowed": False,
            "special_processor": "dispatch_note_service",
            "requires_company_classification": False,
            "requires_tax_analysis": False,
            "required_fields": [
                "document_number",
                "document_date",
            ],
        },
        "PROFORMA_INVOICE": {
            "display_name": "Proforma Fatura",
            "family": "informational_document",
            "accounting_effect": "none",
            "posting_allowed": False,
            "special_processor": "",
            "requires_company_classification": False,
            "requires_tax_analysis": False,
            "required_fields": [],
        },
        "UNKNOWN_DOCUMENT": {
            "display_name": "Tanımlanamayan Belge",
            "family": "unknown",
            "accounting_effect": "unknown",
            "posting_allowed": False,
            "special_processor": "",
            "requires_company_classification": False,
            "requires_tax_analysis": False,
            "required_fields": [],
        },
    }

    FIELD_ALIASES = {
        "document_number": [
            "document_number",
            "invoice_number",
            "receipt_number",
            "policy_number",
        ],
        "invoice_number": [
            "invoice_number",
            "document_number",
        ],
        "document_date": [
            "document_date",
            "invoice_date",
            "issue_date",
        ],
        "invoice_date": [
            "invoice_date",
            "document_date",
            "issue_date",
        ],
        "seller_tax_number": [
            "seller_tax_number",
            "issuer_tax_number",
            "provider_tax_number",
        ],
        "payable_amount": [
            "payable_amount",
            "total_amount",
            "net_amount",
            "amount",
        ],
        "tax_base_amount": [
            "tax_base_amount",
            "accounting_base_amount",
            "subtotal",
        ],
        "vat_amount": [
            "vat_amount",
        ],
        "oiv_amount": [
            "oiv_amount",
            "special_communication_tax",
        ],
    }

    def classify(
        self,
        document_data: dict,
        file_name: str = "",
    ) -> dict:
        """
        Belge türünü belirler.
        """

        search_text = self._build_search_text(
            document_data=document_data,
            file_name=file_name,
        )

        explicit_result = self._explicit_classification(
            document_data
        )

        if explicit_result:
            document_code = explicit_result
            confidence = 99
            matched_signals = [
                "Belge servisinden gelen açık tür bilgisi"
            ]

        else:
            candidates = self._build_candidates(
                search_text=search_text,
                document_data=document_data,
            )

            candidates.sort(
                key=lambda item: item["score"],
                reverse=True,
            )

            best_candidate = candidates[0]

            document_code = best_candidate[
                "document_code"
            ]
            confidence = best_candidate["score"]
            matched_signals = best_candidate[
                "matched_signals"
            ]

        definition = dict(
            self.DOCUMENT_DEFINITIONS[
                document_code
            ]
        )

        subtype = self._detect_subtype(
            document_code=document_code,
            search_text=search_text,
            document_data=document_data,
        )

        validation = self.validate_document(
            document_code=document_code,
            document_data=document_data,
        )

        warnings = list(
            validation["warnings"]
        )

        posting_blocked = (
            not definition["posting_allowed"]
            or confidence < 60
            or not validation["is_valid"]
        )

        if confidence < 60:
            warnings.append(
                "Belge türü düşük güvenle belirlendi."
            )

        if not definition["posting_allowed"]:
            warnings.append(
                "Bu belge tek başına muhasebe fişi oluşturmaz."
            )

        return {
            "registry_version": self.REGISTRY_VERSION,
            "document_code": document_code,
            "document_name": definition[
                "display_name"
            ],
            "document_family": definition[
                "family"
            ],
            "document_subtype": subtype,
            "confidence": confidence,
            "matched_signals": matched_signals,
            "accounting_effect": definition[
                "accounting_effect"
            ],
            "posting_allowed": definition[
                "posting_allowed"
            ],
            "posting_blocked": posting_blocked,
            "special_processor": definition[
                "special_processor"
            ],
            "requires_company_classification": (
                definition[
                    "requires_company_classification"
                ]
            ),
            "requires_tax_analysis": definition[
                "requires_tax_analysis"
            ],
            "required_fields": definition[
                "required_fields"
            ],
            "missing_fields": validation[
                "missing_fields"
            ],
            "warnings": warnings,
            "reason": self._build_reason(
                document_code=document_code,
                confidence=confidence,
                matched_signals=matched_signals,
            ),
        }

    def validate_document(
        self,
        *,
        document_code: str,
        document_data: dict,
    ) -> dict:
        definition = self.DOCUMENT_DEFINITIONS.get(
            document_code,
            self.DOCUMENT_DEFINITIONS[
                "UNKNOWN_DOCUMENT"
            ],
        )

        missing_fields = []

        for field_name in definition.get(
            "required_fields",
            [],
        ):
            if self._get_field_value(
                document_data,
                field_name,
            ) in {
                None,
                "",
                "-",
                "0",
                "0.00",
                "0,00",
                "0.00 TL",
                "0,00 TL",
            }:
                missing_fields.append(
                    field_name
                )

        warnings = [
            f"Zorunlu alan okunamadı: {field_name}"
            for field_name in missing_fields
        ]

        return {
            "is_valid": not missing_fields,
            "missing_fields": missing_fields,
            "warnings": warnings,
        }

    def get_definition(
        self,
        document_code: str,
    ) -> dict:
        return dict(
            self.DOCUMENT_DEFINITIONS.get(
                document_code,
                self.DOCUMENT_DEFINITIONS[
                    "UNKNOWN_DOCUMENT"
                ],
            )
        )

    def _explicit_classification(
        self,
        document_data: dict,
    ) -> str:
        scenario_hint = str(
            document_data.get(
                "document_scenario_hint",
                "",
            )
        ).strip().upper()

        category = str(
            document_data.get(
                "document_category",
                "",
            )
        ).strip().casefold()

        if (
            scenario_hint == "TELECOM_INVOICE"
            or category == "telecom"
        ):
            return "TELECOM_INVOICE"

        if (
            scenario_hint == "FACTORING_INVOICE"
            or category == "factoring"
        ):
            return "FACTORING_DOCUMENT"

        return ""

    def _build_candidates(
        self,
        *,
        search_text: str,
        document_data: dict,
    ) -> list[dict]:
        candidates = []

        candidates.append(
            self._candidate(
                "TELECOM_INVOICE",
                search_text,
                [
                    "ttnet",
                    "türk telekom",
                    "turk telekom",
                    "özel iletişim vergisi",
                    "öiv",
                    "hizmet no",
                    "dsl(internet)",
                ],
                base_score=20,
                signal_score=15,
            )
        )

        candidates.append(
            self._candidate(
                "FACTORING_DOCUMENT",
                search_text,
                [
                    "faktoring",
                    "factoring",
                    "faktoring komisyonu",
                    "faktoring faizi",
                    "iskonto faizi",
                    "bsmv",
                    (
                        "banka ve sigorta "
                        "muameleleri vergisi"
                    ),
                ],
                base_score=20,
                signal_score=17,
            )
        )

        candidates.append(
            self._candidate(
                "SELF_EMPLOYMENT_RECEIPT",
                search_text,
                [
                    "serbest meslek makbuzu",
                    "e-serbest meslek makbuzu",
                    "e-smm",
                    "mesleki tahsilat",
                ],
                base_score=25,
                signal_score=25,
            )
        )

        candidates.append(
            self._candidate(
                "EXPENSE_VOUCHER",
                search_text,
                [
                    "gider pusulası",
                    "e-gider pusulası",
                    "gider pusulasi",
                ],
                base_score=25,
                signal_score=30,
            )
        )

        candidates.append(
            self._candidate(
                "PRODUCER_RECEIPT",
                search_text,
                [
                    "müstahsil makbuzu",
                    "e-müstahsil makbuzu",
                    "mustahsil makbuzu",
                ],
                base_score=25,
                signal_score=30,
            )
        )

        candidates.append(
            self._candidate(
                "RETAIL_RECEIPT",
                search_text,
                [
                    "perakende satış fişi",
                    "perakende satis fisi",
                    "ödeme kaydedici cihaz",
                    "ö.k.c.",
                    "okc fişi",
                    "yazar kasa fişi",
                ],
                base_score=20,
                signal_score=22,
            )
        )

        candidates.append(
            self._candidate(
                "PASSENGER_TICKET",
                search_text,
                [
                    "yolcu bileti",
                    "e-bilet",
                    "boarding pass",
                    "uçuş bileti",
                    "otobüs bileti",
                ],
                base_score=20,
                signal_score=25,
            )
        )

        candidates.append(
            self._candidate(
                "BANK_RECEIPT",
                search_text,
                [
                    "banka dekontu",
                    "işlem dekontu",
                    "havale",
                    "eft",
                    "fast işlemi",
                    "gönderen iban",
                    "alıcı iban",
                ],
                base_score=15,
                signal_score=14,
            )
        )

        candidates.append(
            self._candidate(
                "INSURANCE_POLICY",
                search_text,
                [
                    "sigorta poliçesi",
                    "poliçe no",
                    "sigorta ettiren",
                    "sigortalı",
                    "prim toplamı",
                ],
                base_score=20,
                signal_score=17,
            )
        )

        candidates.append(
            self._candidate(
                "PAYROLL",
                search_text,
                [
                    "ücret bordrosu",
                    "maaş bordrosu",
                    "bordro dönemi",
                    "sgk matrahı",
                    "net ücret",
                ],
                base_score=20,
                signal_score=20,
            )
        )

        candidates.append(
            self._candidate(
                "DISPATCH_NOTE",
                search_text,
                [
                    "sevk irsaliyesi",
                    "e-irsaliye",
                    "taşıma irsaliyesi",
                    "irsaliye no",
                    "sevk tarihi",
                ],
                base_score=20,
                signal_score=22,
            )
        )

        candidates.append(
            self._candidate(
                "PROFORMA_INVOICE",
                search_text,
                [
                    "proforma fatura",
                    "proforma invoice",
                    "ticari teklif",
                ],
                base_score=25,
                signal_score=30,
            )
        )

        invoice_candidate = self._candidate(
            "INVOICE",
            search_text,
            [
                "e-fatura",
                "e-arşiv fatura",
                "e-arsiv fatura",
                "fatura no",
                "fatura tarihi",
                "fatura tipi",
                "ettn",
                "ödenecek tutar",
                "mal hizmet toplam",
            ],
            base_score=10,
            signal_score=10,
        )

        if document_data.get(
            "invoice_number"
        ):
            invoice_candidate["score"] += 20
            invoice_candidate[
                "matched_signals"
            ].append(
                "invoice_number alanı"
            )

        if document_data.get("ettn"):
            invoice_candidate["score"] += 20
            invoice_candidate[
                "matched_signals"
            ].append(
                "ETTN alanı"
            )

        invoice_candidate["score"] = min(
            invoice_candidate["score"],
            98,
        )

        candidates.append(invoice_candidate)

        candidates.append({
            "document_code": "UNKNOWN_DOCUMENT",
            "score": 5,
            "matched_signals": [],
        })

        return candidates

    def _candidate(
        self,
        document_code: str,
        search_text: str,
        signals: list[str],
        *,
        base_score: int,
        signal_score: int,
    ) -> dict:
        matched_signals = [
            signal
            for signal in signals
            if self._normalize(signal)
            in search_text
        ]

        score = (
            base_score
            + len(matched_signals)
            * signal_score
        )

        return {
            "document_code": document_code,
            "score": min(score, 98),
            "matched_signals": (
                matched_signals
            ),
        }

    def _detect_subtype(
        self,
        *,
        document_code: str,
        search_text: str,
        document_data: dict,
    ) -> str:
        if document_code == "TELECOM_INVOICE":
            return "telecom_service"

        if document_code == "FACTORING_DOCUMENT":
            return "factoring_finance"

        if document_code != "INVOICE":
            return ""

        invoice_type = self._normalize(
            str(
                document_data.get(
                    "invoice_type",
                    "",
                )
            )
        )

        if (
            "iade" in search_text
            or "iade" in invoice_type
        ):
            return "return"

        if self._contains_any(
            search_text,
            [
                "tevkifat",
                "kdv tevkifatı",
                "tevkifat kodu",
            ],
        ):
            return "withholding"

        if self._contains_any(
            search_text,
            [
                "ihraç kayıtlı",
                "11/1-c",
            ],
        ):
            return "export_registered"

        if self._contains_any(
            search_text,
            [
                "istisna kodu",
                "kdv istisnası",
                "istisna sebebi",
            ],
        ):
            return "vat_exempt"

        return "standard"

    def _get_field_value(
        self,
        document_data: dict,
        field_name: str,
    ):
        aliases = self.FIELD_ALIASES.get(
            field_name,
            [field_name],
        )

        for alias in aliases:
            value = document_data.get(alias)

            if value not in {
                None,
                "",
                "-",
            }:
                return value

        return None

    def _build_search_text(
        self,
        *,
        document_data: dict,
        file_name: str,
    ) -> str:
        parts = [
            file_name,
            document_data.get(
                "file_name",
                "",
            ),
            document_data.get(
                "raw_text",
                "",
            ),
            document_data.get(
                "invoice_type",
                "",
            ),
            document_data.get(
                "scenario",
                "",
            ),
            document_data.get(
                "seller_name",
                "",
            ),
            document_data.get(
                "document_category",
                "",
            ),
        ]

        return self._normalize(
            "\n".join(
                str(part)
                for part in parts
                if part
            )
        )

    def _normalize(
        self,
        value: str,
    ) -> str:
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

        return re.sub(
            r"\s+",
            " ",
            normalized.casefold(),
        ).strip()

    def _contains_any(
        self,
        text: str,
        signals: list[str],
    ) -> bool:
        return any(
            self._normalize(signal) in text
            for signal in signals
        )

    def _build_reason(
        self,
        *,
        document_code: str,
        confidence: int,
        matched_signals: list[str],
    ) -> str:
        document_name = (
            self.DOCUMENT_DEFINITIONS[
                document_code
            ]["display_name"]
        )

        if matched_signals:
            return (
                f"Belge {document_name} olarak "
                "sınıflandırıldı. Eşleşen göstergeler: "
                + ", ".join(
                    matched_signals[:6]
                )
                + f". Güven: %{confidence}."
            )

        return (
            f"Belge {document_name} olarak "
            f"düşük güvenle sınıflandırıldı. "
            f"Güven: %{confidence}."
        )
