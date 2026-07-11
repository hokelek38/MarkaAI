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
        İşlenmiş fatura verisini uçtan uca değerlendirir.

        context içinde işlem türüne özel ek bilgiler gönderilir.

        Örnek:
        {
            "payment_type": "credit",
            "sale_content_type": "goods",
            "purchase_account_code": "150",
            "company_account_policy": {
                "withheld_vat_payable_account": "360"
            }
        }
        """

        context = context or {}

        transaction_result = (
            self.transaction_service.classify_transaction(
                document_data=invoice_data,
                document_direction=document_direction,
            )
        )

        transaction_code = transaction_result.get(
            "transaction_code"
        )

        if transaction_code == "STANDARD_PURCHASE":
            service_result = self._process_standard_purchase(
                invoice_data=invoice_data,
                company_id=company_id,
            )

        elif transaction_code == "STANDARD_SALE":
            service_result = self._process_standard_sale(
                invoice_data=invoice_data,
                context=context,
            )

        elif transaction_code == "WITHHOLDING_PURCHASE":
            service_result = self._process_withholding_purchase(
                invoice_data=invoice_data,
                context=context,
            )

        else:
            return self._unsupported_result(
                transaction_result
            )

        if not service_result.get("matched", True):
            return {
                "success": False,
                "transaction": transaction_result,
                "service_result": service_result,
                "voucher": None,
                "validation": None,
                "errors": service_result.get(
                    "errors",
                    ["Muhasebe önerisi oluşturulamadı."],
                ),
            }

        voucher_data = self._create_voucher(
            company=company,
            invoice_data=invoice_data,
            transaction_result=transaction_result,
            service_result=service_result,
        )

        validation_result = (
            self.validation_service.validate(
                invoice_data=invoice_data,
                accounting_data={
                    "debit_entries": service_result.get(
                        "debit_entries",
                        [],
                    ),
                    "credit_entries": service_result.get(
                        "credit_entries",
                        [],
                    ),
                    "warnings": service_result.get(
                        "warnings",
                        [],
                    ),
                },
                user_approved=False,
            )
        )

        return {
            "success": True,
            "transaction": transaction_result,
            "service_result": service_result,
            "voucher": voucher_data,
            "validation": validation_result,
            "errors": validation_result.get(
                "errors",
                [],
            ),
            "warnings": validation_result.get(
                "warnings",
                [],
            ),
            "requires_user_confirmation": True,
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
            debit_entries=service_result.get(
                "debit_entries",
                [],
            ),
            credit_entries=service_result.get(
                "credit_entries",
                [],
            ),
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