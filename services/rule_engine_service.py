import json
from pathlib import Path


class RuleEngineService:
    """
    JSON dosyasında tanımlanan muhasebe kurallarını çalıştırır.

    Bu servis:
    - Kuralları yükler.
    - Koşulları değerlendirir.
    - Uyan kuralları puanlar.
    - En uygun muhasebe hesabını önerir.
    - Kesin kayıt oluşturmaz.
    """

    def __init__(self):
        project_root = Path(__file__).resolve().parent.parent

        self.rules_file = (
            project_root
            / "data"
            / "rules"
            / "purchase_rules.json"
        )

        self.rule_data = self._load_rules()
        self.rules = self.rule_data.get("rules", [])

    def _load_rules(self) -> dict:
        """
        Satın alma kurallarını JSON dosyasından yükler.
        """

        if not self.rules_file.exists():
            raise FileNotFoundError(
                "Muhasebe kural dosyası bulunamadı:\n"
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
                "Muhasebe kural dosyası geçerli JSON biçiminde değil.\n"
                f"Satır: {error.lineno}, sütun: {error.colno}\n"
                f"Detay: {error.msg}"
            ) from error

    def get_metadata(self) -> dict:
        """
        Kural dosyasının sürüm bilgisini döndürür.
        """

        return self.rule_data.get("metadata", {}).copy()

    def get_all_rules(
        self,
        enabled_only: bool = True,
    ) -> list[dict]:
        """
        Bütün kuralları döndürür.

        enabled_only=True ise yalnızca aktif kurallar gelir.
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
        Kural kimliğine göre tek bir kural döndürür.
        """

        normalized_rule_id = str(rule_id).strip()

        for rule in self.rules:
            if rule.get("rule_id") == normalized_rule_id:
                return rule.copy()

        return None

    def evaluate(
        self,
        facts: dict,
    ) -> dict:
        """
        Verilen bilgiler için uygun muhasebe kuralını bulur.

        facts örneği:

        {
            "activity_type": "manufacturing",
            "document_type": "purchase_invoice",
            "usage": "production"
        }
        """

        normalized_facts = self._normalize_facts(facts)

        matched_rules = []

        for rule in self.get_all_rules(enabled_only=True):
            evaluation = self._evaluate_rule(
                rule=rule,
                facts=normalized_facts,
            )

            if evaluation["matched"]:
                matched_rules.append(evaluation)

        matched_rules.sort(
            key=lambda item: (
                item["priority"],
                item["match_score"],
                item["confidence"],
            ),
            reverse=True,
        )

        if not matched_rules:
            return {
                "matched": False,
                "selected_rule": None,
                "matched_rules": [],
                "account_code": None,
                "confidence": 0,
                "reason": (
                    "Mevcut bilgilerle eşleşen muhasebe kuralı bulunamadı."
                ),
                "requires_user_confirmation": True,
            }

        selected_rule = matched_rules[0]

        return {
            "matched": True,
            "selected_rule": selected_rule,
            "matched_rules": matched_rules,
            "account_code": selected_rule["account_code"],
            "confidence": selected_rule["confidence"],
            "reason": selected_rule["reason"],
            "requires_user_confirmation": True,
        }

    def _evaluate_rule(
        self,
        rule: dict,
        facts: dict,
    ) -> dict:
        """
        Tek bir kuralın bütün koşullarını değerlendirir.
        """

        conditions = rule.get("conditions", {})

        matched_conditions = []
        failed_conditions = []

        for field_name, allowed_values in conditions.items():
            fact_value = facts.get(field_name)

            if not isinstance(allowed_values, list):
                allowed_values = [allowed_values]

            normalized_allowed_values = [
                self._normalize_value(value)
                for value in allowed_values
            ]

            normalized_fact_value = self._normalize_value(
                fact_value
            )

            if normalized_fact_value in normalized_allowed_values:
                matched_conditions.append({
                    "field": field_name,
                    "value": fact_value,
                    "allowed_values": allowed_values,
                })
            else:
                failed_conditions.append({
                    "field": field_name,
                    "value": fact_value,
                    "allowed_values": allowed_values,
                })

        matched = (
            len(conditions) > 0
            and len(failed_conditions) == 0
        )

        result = rule.get("result", {})
        account_code = str(
            result.get("account", "")
        ).strip()

        confidence = int(
            result.get("confidence", 0)
        )

        match_score = len(matched_conditions)

        reason = self._build_reason(
            rule=rule,
            matched_conditions=matched_conditions,
        )

        return {
            "matched": matched,
            "rule_id": rule.get("rule_id", ""),
            "description": rule.get("description", ""),
            "priority": int(rule.get("priority", 0)),
            "account_code": account_code,
            "confidence": confidence,
            "match_score": match_score,
            "matched_conditions": matched_conditions,
            "failed_conditions": failed_conditions,
            "reason": reason,
        }

    def _build_reason(
        self,
        rule: dict,
        matched_conditions: list[dict],
    ) -> str:
        """
        Uygulanan kural için açıklanabilir gerekçe oluşturur.
        """

        condition_texts = []

        for condition in matched_conditions:
            field_name = condition["field"]
            value = condition["value"]

            condition_texts.append(
                f"{field_name}={value}"
            )

        conditions_summary = ", ".join(
            condition_texts
        )

        description = rule.get(
            "description",
            "Muhasebe kuralı",
        )

        if not conditions_summary:
            return description

        return (
            f"{description}. Eşleşen koşullar: "
            f"{conditions_summary}."
        )

    def _normalize_facts(
        self,
        facts: dict,
    ) -> dict:
        """
        Kural değerlendirmesinde kullanılacak bilgileri normalize eder.
        """

        normalized = {}

        for key, value in facts.items():
            normalized[str(key).strip()] = (
                self._normalize_value(value)
            )

        return normalized

    def _normalize_value(self, value):
        """
        Metin karşılaştırmalarını büyük-küçük harften bağımsız hale getirir.
        """

        if value is None:
            return None

        if isinstance(value, str):
            return value.strip().casefold()

        return value

    def validate_rules(self) -> dict:
        """
        Kural dosyasındaki temel yapısal hataları kontrol eder.
        """

        errors = []
        warnings = []
        rule_ids = set()

        for index, rule in enumerate(
            self.rules,
            start=1,
        ):
            rule_id = str(
                rule.get("rule_id", "")
            ).strip()

            if not rule_id:
                errors.append(
                    f"{index}. kuralda rule_id bulunmuyor."
                )

            elif rule_id in rule_ids:
                errors.append(
                    f"Mükerrer rule_id bulundu: {rule_id}"
                )

            else:
                rule_ids.add(rule_id)

            if not rule.get("description"):
                warnings.append(
                    f"{rule_id or index} kuralında açıklama bulunmuyor."
                )

            conditions = rule.get("conditions")

            if not isinstance(conditions, dict) or not conditions:
                errors.append(
                    f"{rule_id or index} kuralında geçerli koşul bulunmuyor."
                )

            result = rule.get("result", {})

            if not result.get("account"):
                errors.append(
                    f"{rule_id or index} kuralında sonuç hesabı bulunmuyor."
                )

            confidence = result.get("confidence")

            if not isinstance(confidence, int):
                errors.append(
                    f"{rule_id or index} kuralında güven oranı tam sayı değil."
                )

            elif not 0 <= confidence <= 100:
                errors.append(
                    f"{rule_id or index} kuralında güven oranı 0-100 arasında değil."
                )

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "rule_count": len(self.rules),
        }