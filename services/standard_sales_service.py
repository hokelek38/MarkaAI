import json
from pathlib import Path

from services.accounting_knowledge_service import (
    AccountingKnowledgeService,
)


class StandardSalesService:
    """
    Standart yurt içi satış faturaları için uygun muhasebe
    kuralını bulur ve taslak fiş önerisi üretir.

    Bu servis:
    - Yalnızca STANDARD_SALE işlemlerinde çalışır.
    - Tevkifat, iade, ihracat, ihraç kayıtlı satış ve
      istisnalı satışlarda kullanılmaz.
    - Kesin kayıt oluşturmaz.
    - Mali müşavir onayı olmadan aktarım yapılmasına izin vermez.
    """

    def __init__(self):
        project_root = Path(__file__).resolve().parent.parent

        self.rules_file = (
            project_root
            / "data"
            / "rules"
            / "standard_sales_rules.json"
        )

        self.knowledge_service = AccountingKnowledgeService()

        self.rule_data = self._load_rules()
        self.rules = self.rule_data.get("rules", [])
        self.validation_rules = self.rule_data.get(
            "validation_rules",
            [],
        )

    def _load_rules(self) -> dict:
        """
        Standart satış kurallarını JSON dosyasından yükler.
        """

        if not self.rules_file.exists():
            raise FileNotFoundError(
                "Standart satış kural dosyası bulunamadı:\n"
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
                "Standart satış kural dosyası geçerli JSON değil.\n"
                f"Satır: {error.lineno}, sütun: {error.colno}\n"
                f"Detay: {error.msg}"
            ) from error

    def get_metadata(self) -> dict:
        return self.rule_data.get("metadata", {}).copy()

    def get_all_rules(
        self,
        enabled_only: bool = True,
    ) -> list[dict]:
        """
        Standart satış kurallarını döndürür.
        """

        if not enabled_only:
            return [
                rule.copy()
                for rule in self.rules
            ]

        return [
            rule.copy()
            for rule in self.rules
            if rule.get("enabled") is True
        ]

    def get_rule(
        self,
        rule_id: str,
    ) -> dict | None:
        """
        Kural kimliğine göre tek kural döndürür.
        """

        normalized_rule_id = str(rule_id).strip()

        for rule in self.rules:
            if rule.get("rule_id") == normalized_rule_id:
                return rule.copy()

        return None

    def create_suggestion(
        self,
        sale_data: dict,
        company_account_policy: dict | None = None,
    ) -> dict:
        """
        Standart satış bilgilerine göre muhasebe fişi önerisi üretir.

        sale_data örneği:

        {
            "transaction_code": "STANDARD_SALE",
            "direction": "sale",
            "tax_scenario": "standard_vat",
            "payment_type": "credit",
            "sale_content_type": "goods",
            "invoice_number": "ABC2026000000001",
            "invoice_date": "11-07-2026",
            "buyer_tax_number": "1234567890",
            "subtotal": "10.000,00 TL",
            "vat_amount": "2.000,00 TL",
            "total_amount": "12.000,00 TL"
        }
        """

        company_account_policy = company_account_policy or {}

        safety_result = self._validate_standard_sale_scope(
            sale_data
        )

        if not safety_result["is_valid"]:
            return {
                "matched": False,
                "can_create_voucher": False,
                "errors": safety_result["errors"],
                "warnings": safety_result["warnings"],
                "debit_entries": [],
                "credit_entries": [],
                "requires_user_confirmation": True,
            }

        matching_rules = []

        for rule in self.get_all_rules(
            enabled_only=True
        ):
            result = self._evaluate_rule(
                rule=rule,
                sale_data=sale_data,
            )

            if result["matched"]:
                matching_rules.append(result)

        matching_rules.sort(
            key=lambda result: (
                result["priority"],
                result["condition_count"],
                result["confidence"],
            ),
            reverse=True,
        )

        if not matching_rules:
            return {
                "matched": False,
                "can_create_voucher": False,
                "errors": [
                    "Satış bilgilerine uyan standart satış kuralı bulunamadı."
                ],
                "warnings": [
                    "Ödeme şekli ve satış içeriği kullanıcı tarafından kontrol edilmelidir."
                ],
                "debit_entries": [],
                "credit_entries": [],
                "requires_user_confirmation": True,
            }

        selected_rule = matching_rules[0]["rule"]

        entries = self._build_entries(
            rule=selected_rule,
            sale_data=sale_data,
            company_account_policy=company_account_policy,
        )

        warnings = list(
            safety_result["warnings"]
        )

        warnings.extend(
            entries["warnings"]
        )

        warnings.append(
            "100, 102 veya 120 hesabı gerçek tahsilat durumuna göre doğrulanmalıdır."
        )

        warnings.append(
            "Mali müşavir onayı olmadan satış fişi kesinleştirilemez."
        )

        return {
            "matched": True,
            "rule_id": selected_rule.get("rule_id"),
            "rule_description": selected_rule.get(
                "description",
                "",
            ),
            "confidence": int(
                selected_rule.get("confidence", 0)
            ),
            "debit_entries": entries["debit_entries"],
            "credit_entries": entries["credit_entries"],
            "warnings": self._unique_values(warnings),
            "errors": entries["errors"],
            "can_create_voucher": (
                len(entries["errors"]) == 0
            ),
            "requires_user_confirmation": True,
            "reason": self._build_reason(
                selected_rule,
                sale_data,
            ),
        }

    def _validate_standard_sale_scope(
        self,
        sale_data: dict,
    ) -> dict:
        """
        Belgenin standart satış kuralları kapsamında olup olmadığını kontrol eder.
        """

        errors = []
        warnings = []

        transaction_code = str(
            sale_data.get("transaction_code", "")
        ).strip()

        if transaction_code != "STANDARD_SALE":
            errors.append(
                "Bu servis yalnızca STANDARD_SALE işleminde kullanılabilir."
            )

        direction = str(
            sale_data.get("direction", "")
        ).strip()

        if direction != "sale":
            errors.append(
                "Belge işletme açısından satış yönünde değil."
            )

        tax_scenario = str(
            sale_data.get("tax_scenario", "")
        ).strip()

        if tax_scenario != "standard_vat":
            errors.append(
                "Belge standart KDV senaryosunda değil."
            )

        raw_text = str(
            sale_data.get("raw_text", "")
        ).casefold()

        special_scenario_keywords = [
            "tevkifat",
            "ihraç kayıtlı",
            "iade faturası",
            "kdv istisnası",
            "istisna kodu",
            "ihracat",
            "özel matrah",
        ]

        detected_special_keywords = [
            keyword
            for keyword in special_scenario_keywords
            if keyword in raw_text
        ]

        if detected_special_keywords:
            errors.append(
                "Belgede standart satış dışında özel işlem işaretleri bulundu: "
                + ", ".join(detected_special_keywords)
            )

        required_fields = [
            "invoice_number",
            "invoice_date",
            "buyer_tax_number",
            "subtotal",
            "total_amount",
        ]

        for field_name in required_fields:
            if self._is_empty_value(
                sale_data.get(field_name)
            ):
                errors.append(
                    f"Zorunlu alan eksik: {field_name}"
                )

        if self._is_empty_value(
            sale_data.get("payment_type")
        ):
            errors.append(
                "Ödeme şekli belirlenmedi."
            )

        if self._is_empty_value(
            sale_data.get("sale_content_type")
        ):
            warnings.append(
                "Satışın mal veya hizmet niteliği belirlenmedi."
            )

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def _evaluate_rule(
        self,
        rule: dict,
        sale_data: dict,
    ) -> dict:
        """
        Satış verisinin tek bir kurala uyup uymadığını değerlendirir.
        """

        conditions = rule.get("conditions", {})

        matched_conditions = []
        failed_conditions = []

        for field_name, allowed_values in conditions.items():
            if not isinstance(allowed_values, list):
                allowed_values = [allowed_values]

            actual_value = self._normalize_value(
                sale_data.get(field_name)
            )

            normalized_allowed_values = [
                self._normalize_value(value)
                for value in allowed_values
            ]

            if actual_value in normalized_allowed_values:
                matched_conditions.append(field_name)
            else:
                failed_conditions.append(field_name)

        return {
            "matched": (
                len(conditions) > 0
                and not failed_conditions
            ),
            "priority": int(
                rule.get("priority", 0)
            ),
            "confidence": int(
                rule.get("confidence", 0)
            ),
            "condition_count": len(
                matched_conditions
            ),
            "matched_conditions": matched_conditions,
            "failed_conditions": failed_conditions,
            "rule": rule,
        }

    def _build_entries(
        self,
        rule: dict,
        sale_data: dict,
        company_account_policy: dict,
    ) -> dict:
        """
        Seçilen JSON kuralından borç ve alacak fiş satırlarını oluşturur.
        """

        debit_entries = []
        credit_entries = []
        errors = []
        warnings = []

        entries = rule.get("entries", {})

        for entry_definition in entries.get(
            "debit",
            [],
        ):
            entry_result = self._create_entry_from_definition(
                entry_definition=entry_definition,
                sale_data=sale_data,
                company_account_policy=company_account_policy,
            )

            if entry_result["entry"]:
                debit_entries.append(
                    entry_result["entry"]
                )

            errors.extend(
                entry_result["errors"]
            )

            warnings.extend(
                entry_result["warnings"]
            )

        for entry_definition in entries.get(
            "credit",
            [],
        ):
            entry_result = self._create_entry_from_definition(
                entry_definition=entry_definition,
                sale_data=sale_data,
                company_account_policy=company_account_policy,
            )

            if entry_result["entry"]:
                credit_entries.append(
                    entry_result["entry"]
                )

            errors.extend(
                entry_result["errors"]
            )

            warnings.extend(
                entry_result["warnings"]
            )

        return {
            "debit_entries": debit_entries,
            "credit_entries": credit_entries,
            "errors": errors,
            "warnings": warnings,
        }

    def _create_entry_from_definition(
        self,
        entry_definition: dict,
        sale_data: dict,
        company_account_policy: dict,
    ) -> dict:
        """
        JSON fiş satırı tanımını gerçek muhasebe satırına dönüştürür.
        """

        errors = []
        warnings = []

        if entry_definition.get(
            "dynamic_split"
        ):
            warnings.append(
                "Karma tahsilat dağılımı henüz otomatik oluşturulmadı."
            )

            return {
                "entry": None,
                "errors": errors,
                "warnings": warnings,
            }

        include_when = entry_definition.get(
            "include_when",
            {},
        )

        if include_when.get(
            "vat_amount_positive"
        ):
            vat_amount = sale_data.get(
                "vat_amount",
                "-",
            )

            if not self._has_positive_amount(
                vat_amount
            ):
                return {
                    "entry": None,
                    "errors": errors,
                    "warnings": warnings,
                }

        account_code = entry_definition.get(
            "account"
        )

        if not account_code:
            policy_key = entry_definition.get(
                "account_policy_key"
            )

            account_code = company_account_policy.get(
                policy_key
            )

            if not account_code:
                account_code = entry_definition.get(
                    "fallback_account"
                )

                warnings.append(
                    f"{policy_key} firma politikasında bulunamadığı için "
                    f"{account_code} geçici hesap olarak kullanıldı."
                )

        account = self.knowledge_service.get_account(
            account_code
        )

        if not account:
            errors.append(
                "Satış kuralında kullanılan hesap bilgi tabanında bulunamadı: "
                f"{account_code}"
            )

            return {
                "entry": None,
                "errors": errors,
                "warnings": warnings,
            }

        amount_source = entry_definition.get(
            "amount_source"
        )

        amount = sale_data.get(
            amount_source,
            "-",
        )

        if self._is_empty_value(amount):
            errors.append(
                f"{account_code} hesabı için tutar bulunamadı: "
                f"{amount_source}"
            )

        return {
            "entry": {
                "account_code": account.get("code"),
                "account_name": account.get("name"),
                "amount": amount,
                "description": entry_definition.get(
                    "description",
                    "",
                ),
                "verified": account.get(
                    "verified",
                    False,
                ),
            },
            "errors": errors,
            "warnings": warnings,
        }

    def _build_reason(
        self,
        rule: dict,
        sale_data: dict,
    ) -> str:
        """
        Uygulanan satış kuralının açıklamasını oluşturur.
        """

        return (
            f"{rule.get('description', 'Standart satış kuralı')} "
            f"uygulandı. Ödeme şekli: "
            f"{sale_data.get('payment_type', '-')}, "
            f"satış içeriği: "
            f"{sale_data.get('sale_content_type', '-')}."
        )

    def _normalize_value(self, value):
        if value is None:
            return None

        if isinstance(value, str):
            return value.strip().casefold()

        return value

    def _is_empty_value(self, value) -> bool:
        if value is None:
            return True

        if isinstance(value, str):
            return value.strip() in {
                "",
                "-",
            }

        if isinstance(value, (list, dict)):
            return len(value) == 0

        return False

    def _has_positive_amount(
        self,
        amount,
    ) -> bool:
        try:
            normalized = (
                str(amount)
                .replace("TL", "")
                .replace("₺", "")
                .replace(" ", "")
                .replace(".", "")
                .replace(",", ".")
            )

            return float(normalized) > 0

        except (TypeError, ValueError):
            return False

    def _unique_values(
        self,
        values: list[str],
    ) -> list[str]:
        unique_values = []

        for value in values:
            if value and value not in unique_values:
                unique_values.append(value)

        return unique_values