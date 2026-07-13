from decimal import Decimal, InvalidOperation
from services.accounting_service import AccountingService
from services.knowledge_fusion_service import KnowledgeFusionService
from services.standard_sales_service import StandardSalesService
from services.transaction_type_service import TransactionTypeService
from services.voucher_engine import VoucherEngine
from services.voucher_validation_service import (
    VoucherValidationService,
)
from services.withholding_purchase_service import (
    WithholdingPurchaseService,
)

from services.line_accounting_service import LineAccountingService
from services.document_scenario_service import DocumentScenarioService

from services.document_registry_service import DocumentRegistryService
from services.company_classification_service import CompanyClassificationService


class DecisionEngine:
    """
    MarkaAI çekirdek orkestratörü.

    Belge verisini:
    1. İşlem türüne ayırır.
    2. Uygun muhasebe servisine yönlendirir.
    3. MSV fişini oluşturur.
    4. Doğrulama sonucunu ekler.

    UI katmanı ileride yalnızca bu servisi çağıracaktır.
    """

    def _handle_document_registry_result(
        self,
        *,
        registry_result: dict,
    ) -> dict | None:
        """
        Muhasebe kaydı oluşturamayacak belgeleri
        karar motoruna geçmeden durdurur.
        """

        posting_blocked = registry_result.get(
            "posting_blocked",
            True,
        )

        if not posting_blocked:
            return None

        document_name = str(
            registry_result.get(
                "document_name",
                "Tanımlanamayan belge",
            )
        )

        confidence = int(
            registry_result.get(
                "confidence",
                0,
            )
            or 0
        )

        errors = []

        if not registry_result.get(
            "posting_allowed",
            False,
        ):
            errors.append(
                f"{document_name} tek başına "
                "muhasebe fişi oluşturamaz."
            )

        if confidence < 60:
            errors.append(
                "Belge türü yeterli güvenle "
                "tanımlanamadı."
            )

        for field_name in registry_result.get(
            "missing_fields",
            [],
        ):
            errors.append(
                "Belgedeki zorunlu alan "
                f"okunamadı: {field_name}"
            )

        if not errors:
            errors.append(
                "Belge sicili muhasebe kaydının "
                "oluşturulmasına izin vermedi."
            )

        return {
            "success": False,
            "document_registry": registry_result,
            "document_scenario": None,
            "transaction": None,
            "service_result": None,
            "voucher": None,
            "validation": None,
            "errors": errors,
            "warnings": list(
                registry_result.get(
                    "warnings",
                    [],
                )
            ),
            "requires_user_confirmation": True,
        }

    def _handle_company_classification_result(
        self,
        *,
        classification_result: dict,
        document_registry_result: dict,
    ) -> dict | None:
        """
        Firmanın faaliyet türü güvenli şekilde
        belirlenmediyse muhasebe kaydını durdurur.
        """

        posting_allowed = (
            classification_result.get(
                "posting_allowed",
                False,
            )
        )

        requires_confirmation = (
            classification_result.get(
                "requires_user_confirmation",
                True,
            )
        )

        if (
            posting_allowed
            and not requires_confirmation
        ):
            return None

        company_title = str(
            classification_result.get(
                "company_title",
                "Firma",
            )
            or "Firma"
        )

        errors = []

        if not posting_allowed:
            errors.append(
                f"{company_title} için faaliyet türü "
                "belirlenemedi."
            )

        if requires_confirmation:
            errors.append(
                "Firma faaliyet sınıflandırması "
                "kullanıcı tarafından doğrulanmalıdır."
            )

        return {
            "success": False,
            "document_registry": (
                document_registry_result
            ),
            "company_classification": (
                classification_result
            ),
            "document_scenario": None,
            "transaction": None,
            "service_result": None,
            "voucher": None,
            "validation": None,
            "errors": errors,
            "warnings": list(
                classification_result.get(
                    "warnings",
                    [],
                )
            ),
            "requires_user_confirmation": True,
        }

    def __init__(self):
        self.transaction_service = TransactionTypeService()
        self.accounting_service = AccountingService()
        self.fusion_service = KnowledgeFusionService()
        self.standard_sales_service = StandardSalesService()
        self.withholding_purchase_service = (
            WithholdingPurchaseService()
        )
        self.voucher_engine = VoucherEngine()
        self.validation_service = VoucherValidationService()
        self.document_scenario_service = (
            DocumentScenarioService()
        )
        self.document_registry_service = (
            DocumentRegistryService()
        )
        self.company_classification_service = (
            CompanyClassificationService()
        )

    def process_invoice(
        self,
        *,
        invoice_data: dict,
        company: dict,
        company_id: str,
        document_direction: str | None = None,
        context: dict | None = None,
    ) -> dict:
        """
        Belgeyi ve firmayı sınıflandırdıktan sonra
        muhasebe önerisi oluşturur.
        """

        context = context or {}

        company_profile = (
            company
            if isinstance(company, dict)
            else {}
        )

        invoice_data = (
            self._prepare_invoice_amounts(
                invoice_data
            )
        )

        # 1. Önce belgenin gerçek türünü tanı.
        document_registry_result = (
            self.document_registry_service.classify(
                document_data=invoice_data,
                file_name=str(
                    invoice_data.get(
                        "file_name",
                        "",
                    )
                ),
            )
        )

        invoice_data[
            "document_registry"
        ] = document_registry_result

        blocked_document_result = (
            self._handle_document_registry_result(
                registry_result=(
                    document_registry_result
                ),
            )
        )

        if blocked_document_result is not None:
            return blocked_document_result

        # 2. Firmayı imalat, ticaret, hizmet
        # veya karma faaliyet olarak sınıflandır.
        company_classification_result = (
            self.company_classification_service
            .classify(
                company_profile
            )
        )

        invoice_data[
            "company_classification"
        ] = company_classification_result

        blocked_company_result = (
            self._handle_company_classification_result(
                classification_result=(
                    company_classification_result
                ),
                document_registry_result=(
                    document_registry_result
                ),
            )
        )

        if blocked_company_result is not None:
            return blocked_company_result

        # 3. Belgenin muhasebe işlem türünü belirle.
        transaction_result = (
            self.transaction_service
            .classify_transaction(
                document_data=invoice_data,
                document_direction=(
                    document_direction
                ),
            )
        )

        transaction_code = (
            transaction_result.get(
                "transaction_code"
            )
        )

        # 4. Uygun muhasebe servisine yönlendir.
        if transaction_code == "STANDARD_PURCHASE":
            service_result = (
                self._process_standard_purchase(
                    invoice_data=invoice_data,
                    company_id=company_id,
                )
            )

        elif transaction_code == "STANDARD_SALE":
            service_result = (
                self._process_standard_sale(
                    invoice_data=invoice_data,
                    context=context,
                )
            )

        elif (
            transaction_code
            == "WITHHOLDING_PURCHASE"
        ):
            service_result = (
                self._process_withholding_purchase(
                    invoice_data=invoice_data,
                    context=context,
                )
            )

        else:
            unsupported_result = (
                self._unsupported_result(
                    transaction_result
                )
            )

            unsupported_result[
                "document_registry"
            ] = document_registry_result

            unsupported_result[
                "company_classification"
            ] = company_classification_result

            return unsupported_result

        if not service_result.get(
            "matched",
            True,
        ):
            warnings = list(
                service_result.get(
                    "warnings",
                    [],
                )
            )

            warnings.extend(
                company_classification_result.get(
                    "warnings",
                    [],
                )
            )

            return {
                "success": False,
                "document_registry": (
                    document_registry_result
                ),
                "company_classification": (
                    company_classification_result
                ),
                "transaction": (
                    transaction_result
                ),
                "service_result": service_result,
                "voucher": None,
                "validation": None,
                "errors": service_result.get(
                    "errors",
                    [
                        "Muhasebe önerisi "
                        "oluşturulamadı."
                    ],
                ),
                "warnings": list(
                    dict.fromkeys(warnings)
                ),
                "requires_user_confirmation": (
                    True
                ),
            }

        # 5. Muhasebe fişini oluştur.
        voucher_data = self._create_voucher(
            company=company_profile,
            invoice_data=invoice_data,
            transaction_result=(
                transaction_result
            ),
            service_result=service_result,
        )

        if voucher_data.get(
            "blocked",
            False,
        ):
            blocked_warnings = list(
                voucher_data.get(
                    "warnings",
                    [],
                )
            )

            blocked_warnings.extend(
                company_classification_result.get(
                    "warnings",
                    [],
                )
            )

            return {
                "success": False,
                "document_registry": (
                    document_registry_result
                ),
                "company_classification": (
                    company_classification_result
                ),
                "transaction": (
                    transaction_result
                ),
                "service_result": (
                    service_result
                ),
                "voucher": None,
                "validation": None,
                "line_usage_review": {
                    "blocked": True,
                    "unresolved_lines": list(
                        voucher_data.get(
                            "unresolved_lines",
                            [],
                        )
                    ),
                    "classified_lines": list(
                        voucher_data.get(
                            "classified_lines",
                            [],
                        )
                    ),
                },
                "errors": list(
                    voucher_data.get(
                        "errors",
                        [
                            "Fatura kalemlerinin "
                            "kullanım amacı "
                            "kesinleştirilemedi."
                        ],
                    )
                ),
                "warnings": list(
                    dict.fromkeys(
                        blocked_warnings
                    )
                ),
                "requires_user_confirmation": True,
            }

        validation_result = (
            self.validation_service.validate(
                invoice_data=invoice_data,
                accounting_data={
                    "debit_entries": (
                        service_result.get(
                            "debit_entries",
                            [],
                        )
                    ),
                    "credit_entries": (
                        service_result.get(
                            "credit_entries",
                            [],
                        )
                    ),
                    "warnings": (
                        service_result.get(
                            "warnings",
                            [],
                        )
                    ),
                },
                user_approved=False,
            )
        )

        warnings = list(
            validation_result.get(
                "warnings",
                [],
            )
        )

        warnings.extend(
            company_classification_result.get(
                "warnings",
                [],
            )
        )

        return {
            "success": True,
            "document_registry": (
                document_registry_result
            ),
            "company_classification": (
                company_classification_result
            ),
            "transaction": transaction_result,
            "service_result": service_result,
            "voucher": voucher_data,
            "validation": validation_result,
            "errors": validation_result.get(
                "errors",
                [],
            ),
            "warnings": list(
                dict.fromkeys(warnings)
            ),
            "requires_user_confirmation": True,
        }

    def _prepare_invoice_amounts(
        self,
        invoice_data: dict,
    ) -> dict:
        """
        Muhasebe kaydında kullanılacak ana tutarı hazırlar.

        Ana hesap:
        - Öncelikle KDV matrah toplamını kullanır.
        - Matrah okunamazsa mal/hizmet toplamına döner.
        """

        prepared_data = dict(invoice_data)

        tax_base_amount = prepared_data.get(
            "tax_base_amount"
        )

        subtotal = prepared_data.get(
            "subtotal"
        )

        prepared_data["original_subtotal"] = subtotal

        if self._is_valid_amount(
            tax_base_amount
        ):
            prepared_data["subtotal"] = (
                tax_base_amount
            )
            prepared_data[
                "accounting_base_amount"
            ] = tax_base_amount
            prepared_data[
                "accounting_amount_source"
            ] = "tax_base_amount"

        else:
            prepared_data[
                "accounting_base_amount"
            ] = subtotal
            prepared_data[
                "accounting_amount_source"
            ] = "subtotal_fallback"

        return prepared_data

    def _is_valid_amount(
        self,
        value,
    ) -> bool:
        if value is None:
            return False

        return str(value).strip() not in {
            "",
            "-",
            "0",
            "0,00",
            "0,00 TL",
            "0.00",
        }

    def _process_standard_purchase(
        self,
        *,
        invoice_data: dict,
        company_id: str,
    ) -> dict:
        return self.accounting_service.suggest_accounts(
            invoice_data=invoice_data,
            company_id=company_id,
        )

    def _process_standard_sale(
        self,
        *,
        invoice_data: dict,
        context: dict,
    ) -> dict:
        sale_data = {
            **invoice_data,
            "transaction_code": "STANDARD_SALE",
            "direction": "sale",
            "tax_scenario": "standard_vat",
            "payment_type": context.get(
                "payment_type",
                "credit",
            ),
            "sale_content_type": context.get(
                "sale_content_type",
                "goods",
            ),
        }

        return self.standard_sales_service.create_suggestion(
            sale_data=sale_data,
            company_account_policy=context.get(
                "company_account_policy",
                {},
            ),
        )

    def _process_withholding_purchase(
        self,
        *,
        invoice_data: dict,
        context: dict,
    ) -> dict:
        withholding_data = {
            **invoice_data,
            "transaction_code": "WITHHOLDING_PURCHASE",
            "direction": "purchase",
            "tax_scenario": "partial_withholding",
            "payment_type": context.get(
                "payment_type",
                "credit",
            ),
            "buyer_responsibility_confirmed": context.get(
                "buyer_responsibility_confirmed",
                False,
            ),
            "current_threshold_confirmed": context.get(
                "current_threshold_confirmed",
                False,
            ),
            "withholding_code_confirmed": context.get(
                "withholding_code_confirmed",
                False,
            ),
            "withholding_ratio_confirmed": context.get(
                "withholding_ratio_confirmed",
                False,
            ),
        }

        return (
            self.withholding_purchase_service
            .create_suggestion(
                invoice_data=withholding_data,
                purchase_account_code=context.get(
                    "purchase_account_code",
                    "770",
                ),
                company_account_policy=context.get(
                    "company_account_policy",
                    {},
                ),
            )
        )

    def _build_line_based_purchase_entries(
        self,
        *,
        invoice_data: dict,
        company: dict,
        service_result: dict,
    ) -> dict:
        """
        Fatura kalemlerini ayrı hesaplarda toplar.

        Kalem toplamları fatura matrahıyla eşleşmezse
        mevcut muhasebe önerisine geri dönülür.
        """

        line_items = invoice_data.get(
            "line_items",
            [],
        )

        if not line_items:
            return {
                "applied": False,
                "debit_entries": [],
                "warnings": [
                    (
                        "Fatura kalemleri ayrı satırlar "
                        "halinde okunamadığı için mevcut "
                        "hesap önerisi kullanıldı."
                    )
                ],
                "confidence": 0,
            }

        classified_lines = (
            LineAccountingService()
            .classify_lines(
                line_items=line_items,
                company=company,
            )
        )

        blocking_lines = []

        for line in classified_lines:
            amount = self._parse_invoice_amount(
                line.get(
                    "tax_base",
                    line.get(
                        "line_total",
                        "0",
                    ),
                )
            )

            # Sıfır veya negatif indirim satırları
            # kullanım amacı engeline takılmaz.
            if amount <= Decimal("0.00"):
                continue

            account_code = str(
                line.get(
                    "account_code",
                    "",
                )
            ).strip()

            posting_allowed = bool(
                line.get(
                    "posting_allowed",
                    False,
                )
            )

            if (
                posting_allowed
                and account_code
            ):
                continue

            blocking_lines.append({
                "line_number": line.get(
                    "line_number",
                    "",
                ),
                "description": str(
                    line.get(
                        "description",
                        "",
                    )
                ).strip(),
                "amount": (
                    self._decimal_amount_text(
                        amount
                    )
                ),
                "usage_status": line.get(
                    "usage_status",
                    "unresolved",
                ),
                "usage": line.get(
                    "usage",
                    "",
                ),
                "usage_name": line.get(
                    "usage_name",
                    "Belirlenemedi",
                ),
                "account_code": account_code,
                "reason": line.get(
                    "reason",
                    "",
                ),
                "candidates": list(
                    line.get(
                        "usage_candidates",
                        [],
                    )
                ),
                "warnings": list(
                    line.get(
                        "warnings",
                        [],
                    )
                ),
            })

        if blocking_lines:
            descriptions = [
                item.get(
                    "description",
                    "",
                )
                or "Açıklamasız kalem"
                for item in blocking_lines
            ]

            error_message = (
                f"{len(blocking_lines)} fatura "
                "kaleminin kullanım amacı veya "
                "muhasebe hesabı kesinleştirilemedi."
            )

            return {
                "applied": False,
                "blocked": True,
                "debit_entries": [],
                "classified_lines": (
                    classified_lines
                ),
                "unresolved_lines": (
                    blocking_lines
                ),
                "errors": [
                    error_message,
                    (
                        "Kullanım amacı seçilmeden "
                        "muhasebe fişi oluşturulamaz."
                    ),
                ],
                "warnings": [
                    (
                        "Kontrol edilmesi gereken "
                        "kalemler: "
                        + " / ".join(
                            descriptions[:5]
                        )
                    )
                ],
                "confidence": 0,
                "requires_user_confirmation": True,
            }

        grouped_amounts = {}
        grouped_names = {}
        grouped_descriptions = {}
        confirmation_accounts = set()
        confidence_values = []

        for line in classified_lines:
            amount = self._parse_invoice_amount(
                line.get(
                    "tax_base",
                    line.get(
                        "line_total",
                        "0",
                    ),
                )
            )

            if amount <= Decimal("0.00"):
                continue

            account_code = str(
                line.get(
                    "account_code",
                    "",
                )
            ).strip()

            if not account_code:
                continue

            account_name = str(
                line.get(
                    "account_name",
                    "Muhasebe Hesabı",
                )
            ).strip()

            grouped_amounts[account_code] = (
                grouped_amounts.get(
                    account_code,
                    Decimal("0.00"),
                )
                + amount
            )

            grouped_names[account_code] = (
                account_name
            )

            grouped_descriptions.setdefault(
                account_code,
                [],
            ).append(
                str(
                    line.get(
                        "description",
                        "",
                    )
                ).strip()
            )

            confidence = int(
                line.get(
                    "confidence",
                    0,
                )
                or 0
            )

            confidence_values.append(
                confidence
            )

            if line.get(
                "requires_user_confirmation",
                False,
            ):
                confirmation_accounts.add(
                    account_code
                )

        if not grouped_amounts:
            return {
                "applied": False,
                "debit_entries": [],
                "warnings": [
                    (
                        "Okunan fatura kalemlerinden "
                        "geçerli bir matrah oluşturulamadı."
                    )
                ],
                "confidence": 0,
            }

        line_total = sum(
            grouped_amounts.values(),
            Decimal("0.00"),
        )

        expected_total = Decimal("0.00")

        for amount_key in [
            "accounting_base_amount",
            "tax_base_amount",
            "subtotal",
        ]:
            candidate = self._parse_invoice_amount(
                invoice_data.get(
                    amount_key,
                    "0",
                )
            )

            if candidate > Decimal("0.00"):
                expected_total = candidate
                break

        if expected_total <= Decimal("0.00"):
            return {
                "applied": False,
                "debit_entries": [],
                "warnings": [
                    (
                        "Fatura matrah toplamı "
                        "doğrulanamadığı için kalem bazlı "
                        "hesaplar fişe uygulanmadı."
                    )
                ],
                "confidence": 0,
            }

        difference = abs(
            line_total - expected_total
        )

        if difference > Decimal("0.10"):
            return {
                "applied": False,
                "debit_entries": [],
                "warnings": [
                    (
                        "Kalem matrahları toplamı ile "
                        "fatura matrahı eşleşmedi. "
                        f"Kalemler: "
                        f"{self._decimal_amount_text(line_total)}, "
                        f"fatura matrahı: "
                        f"{self._decimal_amount_text(expected_total)}. "
                        "Mevcut hesap önerisi korundu."
                    )
                ],
                "confidence": 0,
            }

        debit_entries = []

        for account_code, amount in (
            grouped_amounts.items()
        ):
            descriptions = [
                description
                for description in (
                    grouped_descriptions.get(
                        account_code,
                        [],
                    )
                )
                if description
            ]

            short_description = " / ".join(
                descriptions[:3]
            )

            if len(descriptions) > 3:
                short_description += (
                    f" ve {len(descriptions) - 3} kalem"
                )

            debit_entries.append({
                "account_code": account_code,
                "account_name": grouped_names.get(
                    account_code,
                    "Muhasebe Hesabı",
                ),
                "amount": self._decimal_amount_text(
                    amount
                ),
                "description": (
                    "Fatura kalemleri: "
                    f"{short_description}"
                ),
                "verified": False,
                "normal_balance": "debit",
                "requires_user_confirmation": (
                    account_code
                    in confirmation_accounts
                ),
            })

        # AccountingService tarafından oluşturulan
        # 191 İndirilecek KDV satırını korur.
        existing_debit_entries = (
            service_result.get(
                "debit_entries",
                [],
            )
        )

        for entry in existing_debit_entries:
            account_code = str(
                entry.get(
                    "account_code",
                    "",
                )
            ).strip()

            if account_code.startswith("191"):
                debit_entries.append(
                    entry
                )

        warnings = []

        if confirmation_accounts:
            warnings.append(
                (
                    "Düşük güvenli veya aktifleştirme "
                    "kontrolü gerektiren hesaplar: "
                    + ", ".join(
                        sorted(
                            confirmation_accounts
                        )
                    )
                )
            )

        warnings.append(
            (
                f"{len(classified_lines)} fatura kalemi "
                f"{len(grouped_amounts)} muhasebe "
                "hesabında birleştirildi."
            )
        )

        confidence = (
            min(confidence_values)
            if confidence_values
            else 0
        )

        return {
            "applied": True,
            "debit_entries": debit_entries,
            "warnings": warnings,
            "confidence": confidence,
        }

    def _parse_invoice_amount(
        self,
        value,
    ) -> Decimal:
        """
        Türkçe veya standart para tutarını Decimal yapar.
        """

        normalized = (
            str(value)
            .replace("TL", "")
            .replace("₺", "")
            .replace(" ", "")
            .strip()
        )

        if normalized in {
            "",
            "-",
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

    def _decimal_amount_text(
        self,
        value: Decimal,
    ) -> str:
        """
        VoucherEngine için standart tutar metni üretir.
        """

        return format(
            value.quantize(
                Decimal("0.01")
            ),
            ".2f",
        )

    def _create_voucher(
        self,
        *,
        company: dict,
        invoice_data: dict,
        transaction_result: dict,
        service_result: dict,
    ) -> dict:
        document = {
            "invoice_number": invoice_data.get(
                "invoice_number",
                "",
            ),
            "invoice_date": invoice_data.get(
                "invoice_date",
                "",
            ),
            "document_type": invoice_data.get(
                "invoice_type",
                "",
            ),
            "ettn": invoice_data.get(
                "ettn",
                "",
            ),
            "file_name": invoice_data.get(
                "file_name",
                "",
            ),
            "source_file_path": invoice_data.get(
                "source_file_path",
                "",
            ),
            "counterparty_title": self._get_counterparty_title(
                invoice_data,
                transaction_result,
            ),
            "counterparty_tax_number": (
                self._get_counterparty_tax_number(
                    invoice_data,
                    transaction_result,
                )
            ),
            "counterparty_role": (
                "customer"
                if transaction_result.get("direction")
                == "sale"
                else "supplier"
            ),
        }

        decision = {
            "confidence": service_result.get(
                "confidence",
                0,
            ),
            "rule_id": service_result.get(
                "rule_id",
                service_result.get(
                    "applied_rule_id",
                    "",
                ),
            ),
            "reason": service_result.get(
                "reason",
                "",
            ),
            "warnings": service_result.get(
                "warnings",
                [],
            ),
        }

        debit_entries = list(
            service_result.get(
                "debit_entries",
                [],
            )
        )

        credit_entries = list(
            service_result.get(
                "credit_entries",
                [],
            )
        )

        if (
            transaction_result.get(
                "transaction_code"
            )
            == "STANDARD_PURCHASE"
        ):
            line_entry_result = (
                self._build_line_based_purchase_entries(
                    invoice_data=invoice_data,
                    company=company,
                    service_result=service_result,
                )
            )

            line_warnings = (
                line_entry_result.get(
                    "warnings",
                    [],
                )
            )

            for warning in line_warnings:
                if warning not in decision["warnings"]:
                    decision["warnings"].append(
                        warning
                    )

            if line_entry_result.get(
                "blocked",
                False,
            ):
                return {
                    "blocked": True,
                    "errors": list(
                        line_entry_result.get(
                            "errors",
                            [],
                        )
                    ),
                    "warnings": list(
                        dict.fromkeys(
                            decision.get(
                                "warnings",
                                [],
                            )
                        )
                    ),
                    "unresolved_lines": list(
                        line_entry_result.get(
                            "unresolved_lines",
                            [],
                        )
                    ),
                    "classified_lines": list(
                        line_entry_result.get(
                            "classified_lines",
                            [],
                        )
                    ),
                    "requires_user_confirmation": True,
                }

            if line_entry_result.get(
                "applied"
            ):
                debit_entries = (
                    line_entry_result[
                        "debit_entries"
                    ]
                )

                line_confidence = int(
                    line_entry_result.get(
                        "confidence",
                        0,
                    )
                    or 0
                )

                current_confidence = int(
                    decision.get(
                        "confidence",
                        0,
                    )
                    or 0
                )

                if line_confidence > 0:
                    if current_confidence > 0:
                        decision["confidence"] = min(
                            current_confidence,
                            line_confidence,
                        )
                    else:
                        decision["confidence"] = (
                            line_confidence
                        )

                decision["reason"] = (
                    str(
                        decision.get(
                            "reason",
                            "",
                        )
                    ).strip()
                    + " Fatura kalemleri ayrı ayrı "
                    "sınıflandırılarak aynı hesaba "
                    "yönlendirilen tutarlar birleştirildi."
                ).strip()

        return self.voucher_engine.create_voucher(
            voucher_type=transaction_result.get(
                "transaction_code",
                "",
            ).lower(),
            company=company,
            document=document,
            transaction={
                "transaction_code": (
                    transaction_result.get(
                        "transaction_code",
                        "",
                    )
                ),
                "transaction_name": (
                    transaction_result.get(
                        "transaction_name",
                        "",
                    )
                ),
                "direction": transaction_result.get(
                    "direction",
                    "",
                ),
                "tax_scenario": (
                    transaction_result.get(
                        "tax_scenario",
                        "",
                    )
                ),
                "currency": invoice_data.get(
                    "currency",
                    "TRY",
                ),
                "exchange_rate": invoice_data.get(
                    "exchange_rate",
                    "1",
                ),
            },
            debit_entries=debit_entries,
            credit_entries=credit_entries,
            decision=decision,
            tax_information=service_result.get(
                "tax_result",
                {},
            ),
            explanation=service_result.get(
                "reason",
                "",
            ),
        )

    def _get_counterparty_title(
        self,
        invoice_data: dict,
        transaction_result: dict,
    ) -> str:
        if transaction_result.get("direction") == "sale":
            return invoice_data.get(
                "buyer_name",
                "",
            )

        return invoice_data.get(
            "seller_name",
            "",
        )

    def _get_counterparty_tax_number(
        self,
        invoice_data: dict,
        transaction_result: dict,
    ) -> str:
        if transaction_result.get("direction") == "sale":
            return invoice_data.get(
                "buyer_tax_number",
                "",
            )

        return invoice_data.get(
            "seller_tax_number",
            "",
        )

    def _unsupported_result(
        self,
        transaction_result: dict,
    ) -> dict:
        transaction_code = transaction_result.get(
            "transaction_code",
            "UNKNOWN",
        )

        return {
            "success": False,
            "transaction": transaction_result,
            "service_result": None,
            "voucher": None,
            "validation": None,
            "errors": [
                (
                    f"{transaction_code} işlem türü "
                    "DecisionEngine'e henüz bağlanmadı."
                )
            ],
            "warnings": [],
            "requires_user_confirmation": True,
        }
