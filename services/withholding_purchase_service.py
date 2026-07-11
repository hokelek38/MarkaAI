import json
from decimal import Decimal
from pathlib import Path

from services.accounting_knowledge_service import (
    AccountingKnowledgeService,
)
from services.tax_engine import TaxEngine


class WithholdingPurchaseService:
    """
    Kısmi KDV tevkifatına tabi alış faturaları için
    hesaplama ve taslak muhasebe fişi önerisi üretir.

    Önemli:
    - Tevkifat kodu, oranı, kapsamı ve parasal sınırı bu servis belirlemez.
    - Bu bilgiler güncel ve sürümlendirilmiş mevzuat verisinden gelmelidir.
    - Mali müşavir onayı olmadan kayıt kesinleştirilemez.
    """

    def __init__(self):
        project_root = Path(__file__).resolve().parent.parent

        self.rules_file = (
            project_root
            / "data"
            / "rules"
            / "withholding_purchase_rules.json"
        )

        self.tax_engine = TaxEngine()
        self.knowledge_service = AccountingKnowledgeService()

        self.rule_data = self._load_rules()
        self.rules = self.rule_data.get("rules", [])
        self.validation_rules = self.rule_data.get(
            "validation_rules",
            [],
        )

    def _load_rules(self) -> dict:
        if not self.rules_file.exists():
            raise FileNotFoundError(
                "Tevkifatlı alış kural dosyası bulunamadı:\n"
                f"{self.rules_file}"
            )

        try:
            with self.rules_file.open(
                "r",
                encoding="utf-8",
            ) as file:
                return json.load(file)

        except json.JSONDecodeError as error:
            raise ValueError(
                "Tevkifatlı alış kural dosyası geçerli JSON değil.\n"
                f"Satır: {error.lineno}, sütun: {error.colno}\n"
                f"Detay: {error.msg}"
            ) from error

    def create_suggestion(
        self,
        invoice_data: dict,
        purchase_account_code: str,
        company_account_policy: dict,
    ) -> dict:
        """
        Tevkifatlı alış için taslak fiş önerisi oluşturur.

        company_account_policy örneği:

        {
            "withheld_vat_payable_account": "360"
        }
        """

        scope_validation = self._validate_scope(invoice_data)

        if not scope_validation["is_valid"]:
            return {
                "matched": False,
                "can_create_voucher": False,
                "errors": scope_validation["errors"],
                "warnings": scope_validation["warnings"],
                "debit_entries": [],
                "credit_entries": [],
                "requires_user_confirmation": True,
            }

        selected_rule = self._select_rule(invoice_data)

        if not selected_rule:
            return {
                "matched": False,
                "can_create_voucher": False,
                "errors": [
                    "Ödeme şekline uygun tevkifatlı alış kuralı bulunamadı."
                ],
                "warnings": [],
                "debit_entries": [],
                "credit_entries": [],
                "requires_user_confirmation": True,
            }

        try:
            tax_result = self.tax_engine.calculate_withholding(
                subtotal=invoice_data["subtotal"],
                vat_rate=invoice_data["vat_rate"],
                numerator=invoice_data[
                    "withholding_numerator"
                ],
                denominator=invoice_data[
                    "withholding_denominator"
                ],
            )

        except Exception as error:
            return {
                "matched": False,
                "can_create_voucher": False,
                "errors": [
                    f"Tevkifat hesabı yapılamadı: {error}"
                ],
                "warnings": [],
                "debit_entries": [],
                "credit_entries": [],
                "requires_user_confirmation": True,
            }

        calculation_validation = self._validate_calculations(
            invoice_data=invoice_data,
            tax_result=tax_result,
        )

        entry_result = self._build_entries(
            rule=selected_rule,
            invoice_data=invoice_data,
            tax_result=tax_result,
            purchase_account_code=purchase_account_code,
            company_account_policy=company_account_policy,
        )

        balance_result = self._validate_balance(
            debit_entries=entry_result["debit_entries"],
            credit_entries=entry_result["credit_entries"],
        )

        errors = []
        errors.extend(calculation_validation["errors"])
        errors.extend(entry_result["errors"])
        errors.extend(balance_result["errors"])

        warnings = list(scope_validation["warnings"])
        warnings.extend(calculation_validation["warnings"])
        warnings.extend(entry_result["warnings"])

        warnings.extend([
            (
                "Tevkifat kodu ve oranı, işlem türü ve alıcı "
                "sorumluluğuyla birlikte güncel mevzuat "
                "verisinden doğrulanmalıdır."
            ),
            (
                "Tevkif edilen KDV'nin beyan dönemi ve "
                "2 No.lu KDV yükümlülüğü ayrıca kontrol edilmelidir."
            ),
            (
                "191 İndirilecek KDV hesabına alınacak tutarın "
                "indirim şartları ayrıca doğrulanmalıdır."
            ),
            (
                "Mali müşavir onayı olmadan fiş kesinleştirilemez "
                "ve ERP sistemine aktarılamaz."
            ),
        ])

        return {
            "matched": True,
            "transaction_code": "WITHHOLDING_PURCHASE",
            "rule_id": selected_rule.get("rule_id"),
            "rule_description": selected_rule.get(
                "description",
                "",
            ),
            "confidence": int(
                selected_rule.get("confidence", 0)
            ),
            "tax_result": {
                "subtotal": self._format_amount(
                    tax_result["subtotal"]
                ),
                "gross_vat_amount": self._format_amount(
                    tax_result["gross_vat"]
                ),
                "withheld_vat_amount": self._format_amount(
                    tax_result["withheld_vat"]
                ),
                "seller_collected_vat_amount": self._format_amount(
                    tax_result["seller_vat"]
                ),
                "supplier_payable_amount": self._format_amount(
                    tax_result["supplier_payable"]
                ),
            },
            "debit_entries": entry_result["debit_entries"],
            "credit_entries": entry_result["credit_entries"],
            "debit_total": self._format_amount(
                balance_result["debit_total"]
            ),
            "credit_total": self._format_amount(
                balance_result["credit_total"]
            ),
            "is_balanced": balance_result["is_balanced"],
            "errors": self._unique_values(errors),
            "warnings": self._unique_values(warnings),
            "can_create_voucher": (
                len(errors) == 0
                and balance_result["is_balanced"]
            ),
            "can_export": False,
            "requires_user_confirmation": True,
            "reason": (
                f"{selected_rule.get('description', '')} kuralı "
                "uygulandı. Vergi hesaplamaları merkezi "
                "TaxEngine tarafından oluşturuldu."
            ),
        }

    def _validate_scope(
        self,
        invoice_data: dict,
    ) -> dict:
        errors = []
        warnings = []

        if (
            str(invoice_data.get("transaction_code", "")).strip()
            != "WITHHOLDING_PURCHASE"
        ):
            errors.append(
                "Bu servis yalnızca WITHHOLDING_PURCHASE "
                "işleminde kullanılabilir."
            )

        if (
            str(invoice_data.get("direction", "")).strip()
            != "purchase"
        ):
            errors.append(
                "Belge işletme açısından alış yönünde değil."
            )

        if (
            str(invoice_data.get("tax_scenario", "")).strip()
            != "partial_withholding"
        ):
            errors.append(
                "Belge kısmi tevkifat senaryosunda değil."
            )

        required_fields = [
            "invoice_number",
            "invoice_date",
            "seller_tax_number",
            "subtotal",
            "vat_rate",
            "withholding_code",
            "withholding_numerator",
            "withholding_denominator",
            "payment_type",
        ]

        for field_name in required_fields:
            if self._is_empty(invoice_data.get(field_name)):
                errors.append(
                    f"Zorunlu alan eksik: {field_name}"
                )

        numerator = self._safe_decimal(
            invoice_data.get("withholding_numerator")
        )
        denominator = self._safe_decimal(
            invoice_data.get("withholding_denominator")
        )

        if numerator is not None and denominator is not None:
            if denominator <= 0:
                errors.append(
                    "Tevkifat oranının paydası sıfırdan büyük olmalıdır."
                )

            elif numerator <= 0 or numerator > denominator:
                errors.append(
                    "Tevkifat oranının payı 0 ile payda arasında olmalıdır."
                )

        if not invoice_data.get(
            "buyer_responsibility_confirmed",
            False,
        ):
            errors.append(
                "Alıcının tevkifat uygulama sorumluluğu doğrulanmadı."
            )

        if not invoice_data.get(
            "current_threshold_confirmed",
            False,
        ):
            errors.append(
                "Güncel tevkifat parasal sınırı doğrulanmadı."
            )

        if not invoice_data.get(
            "withholding_code_confirmed",
            False,
        ):
            errors.append(
                "Tevkifat kodunun güncelliği doğrulanmadı."
            )

        if not invoice_data.get(
            "withholding_ratio_confirmed",
            False,
        ):
            errors.append(
                "Tevkifat oranının güncelliği doğrulanmadı."
            )

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def _select_rule(
        self,
        invoice_data: dict,
    ) -> dict | None:
        payment_type = str(
            invoice_data.get("payment_type", "")
        ).strip().casefold()

        matches = []

        for rule in self.rules:
            if rule.get("enabled") is not True:
                continue

            conditions = rule.get("conditions", {})

            expected_direction = conditions.get(
                "direction",
                [],
            )
            expected_scenario = conditions.get(
                "tax_scenario",
                [],
            )
            expected_payment = conditions.get(
                "payment_type",
                [],
            )

            if (
                "purchase" in expected_direction
                and "partial_withholding" in expected_scenario
                and payment_type in [
                    str(value).casefold()
                    for value in expected_payment
                ]
            ):
                matches.append(rule)

        if not matches:
            return None

        matches.sort(
            key=lambda rule: (
                int(rule.get("priority", 0)),
                int(rule.get("confidence", 0)),
            ),
            reverse=True,
        )

        return matches[0]

    def _validate_calculations(
        self,
        invoice_data: dict,
        tax_result: dict,
    ) -> dict:
        errors = []
        warnings = []

        comparisons = [
            (
                "vat_amount",
                tax_result["gross_vat"],
                "Faturadaki toplam KDV",
            ),
            (
                "withheld_vat_amount",
                tax_result["withheld_vat"],
                "Faturadaki tevkif edilen KDV",
            ),
            (
                "seller_collected_vat_amount",
                tax_result["seller_vat"],
                "Satıcının tahsil edeceği KDV",
            ),
            (
                "payable_amount",
                tax_result["supplier_payable"],
                "Satıcıya ödenecek tutar",
            ),
        ]

        for field_name, calculated_value, description in comparisons:
            document_value = invoice_data.get(field_name)

            if self._is_empty(document_value):
                warnings.append(
                    f"{description} belgede bulunmadığı için "
                    "TaxEngine sonucu kullanıldı."
                )
                continue

            parsed_document_value = self._safe_decimal(
                document_value
            )

            if parsed_document_value is None:
                errors.append(
                    f"{description} geçerli bir tutar değil: "
                    f"{document_value}"
                )
                continue

            difference = abs(
                parsed_document_value - calculated_value
            )

            if difference > Decimal("0.01"):
                errors.append(
                    f"{description} hesaplamayla uyuşmuyor. "
                    f"Belge: {self._format_amount(parsed_document_value)}, "
                    f"Hesaplanan: {self._format_amount(calculated_value)}"
                )

        return {
            "errors": errors,
            "warnings": warnings,
        }

    def _build_entries(
        self,
        rule: dict,
        invoice_data: dict,
        tax_result: dict,
        purchase_account_code: str,
        company_account_policy: dict,
    ) -> dict:
        errors = []
        warnings = []
        debit_entries = []
        credit_entries = []

        purchase_account = self.knowledge_service.get_account(
            purchase_account_code
        )

        if not purchase_account:
            errors.append(
                "Alış hesabı Tek Düzen bilgi tabanında bulunamadı: "
                f"{purchase_account_code}"
            )
        else:
            debit_entries.append(
                self._entry(
                    account=purchase_account,
                    debit=tax_result["subtotal"],
                    credit=Decimal("0.00"),
                    description=(
                        "Mal veya hizmetin niteliğine göre "
                        "belirlenen alış hesabı"
                    ),
                    source="Knowledge Fusion + Rule Engine",
                )
            )

        vat_account = self.knowledge_service.get_account("191")

        if not vat_account:
            errors.append(
                "191 İndirilecek KDV hesabı bilgi tabanında bulunamadı."
            )
        else:
            debit_entries.append(
                self._entry(
                    account=vat_account,
                    debit=tax_result["gross_vat"],
                    credit=Decimal("0.00"),
                    description=(
                        "Tevkifatlı alış belgesindeki toplam "
                        "hesaplanan KDV"
                    ),
                    source="Tax Engine",
                )
            )

        payment_type = str(
            invoice_data.get("payment_type", "")
        ).strip()

        supplier_account_code = (
            "102"
            if payment_type == "bank"
            else "320"
        )

        supplier_account = self.knowledge_service.get_account(
            supplier_account_code
        )

        if not supplier_account:
            errors.append(
                "Satıcı veya banka hesabı bilgi tabanında bulunamadı: "
                f"{supplier_account_code}"
            )
        else:
            credit_entries.append(
                self._entry(
                    account=supplier_account,
                    debit=Decimal("0.00"),
                    credit=tax_result["supplier_payable"],
                    description=(
                        "Satıcıya ödenecek veya banka yoluyla "
                        "ödenen net fatura bedeli"
                    ),
                    source="Tax Engine + Payment Rule",
                )
            )

        withheld_account_code = company_account_policy.get(
            "withheld_vat_payable_account"
        )

        if not withheld_account_code:
            errors.append(
                "Firma hesap politikasında "
                "withheld_vat_payable_account tanımlanmadı."
            )
        else:
            withheld_account = self.knowledge_service.get_account(
                withheld_account_code
            )

            if not withheld_account:
                errors.append(
                    "Tevkif edilen KDV hesabı bilgi tabanında "
                    f"bulunamadı: {withheld_account_code}"
                )
            else:
                credit_entries.append(
                    self._entry(
                        account=withheld_account,
                        debit=Decimal("0.00"),
                        credit=tax_result["withheld_vat"],
                        description=(
                            "Sorumlu sıfatıyla beyan edilecek "
                            "tevkif edilen KDV"
                        ),
                        source="Tax Engine + Company Policy",
                    )
                )

        return {
            "debit_entries": debit_entries,
            "credit_entries": credit_entries,
            "errors": errors,
            "warnings": warnings,
        }

    def _validate_balance(
        self,
        debit_entries: list[dict],
        credit_entries: list[dict],
    ) -> dict:
        debit_total = sum(
            (
                entry["debit_raw"]
                for entry in debit_entries
            ),
            Decimal("0.00"),
        )

        credit_total = sum(
            (
                entry["credit_raw"]
                for entry in credit_entries
            ),
            Decimal("0.00"),
        )

        is_balanced = debit_total == credit_total

        errors = []

        if not is_balanced:
            errors.append(
                "Borç ve alacak toplamları eşit değil. "
                f"Borç: {self._format_amount(debit_total)}, "
                f"Alacak: {self._format_amount(credit_total)}"
            )

        return {
            "is_balanced": is_balanced,
            "debit_total": debit_total,
            "credit_total": credit_total,
            "errors": errors,
        }

    def _entry(
        self,
        account: dict,
        debit: Decimal,
        credit: Decimal,
        description: str,
        source: str,
    ) -> dict:
        return {
            "account_code": account.get("code"),
            "account_name": account.get("name"),
            "debit": self._format_amount(debit),
            "credit": self._format_amount(credit),
            "debit_raw": debit,
            "credit_raw": credit,
            "description": description,
            "source": source,
            "verified": account.get("verified", False),
        }

    def _safe_decimal(
        self,
        value,
    ) -> Decimal | None:
        if self._is_empty(value):
            return None

        try:
            normalized = (
                str(value)
                .replace("TL", "")
                .replace("₺", "")
                .replace(" ", "")
                .replace(".", "")
                .replace(",", ".")
            )

            return Decimal(normalized)

        except Exception:
            return None

    def _format_amount(
        self,
        amount: Decimal,
    ) -> str:
        formatted = f"{amount:,.2f}"

        formatted = (
            formatted
            .replace(",", "_")
            .replace(".", ",")
            .replace("_", ".")
        )

        return f"{formatted} TL"

    def _is_empty(
        self,
        value,
    ) -> bool:
        if value is None:
            return True

        if isinstance(value, str):
            return value.strip() in {
                "",
                "-",
            }

        return False

    def _unique_values(
        self,
        values: list[str],
    ) -> list[str]:
        result = []

        for value in values:
            if value and value not in result:
                result.append(value)

        return result