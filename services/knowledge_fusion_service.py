from services.accounting_knowledge_service import (
    AccountingKnowledgeService,
)
from services.company_profile_service import (
    CompanyProfileService,
)
from services.product_knowledge_service import (
    ProductKnowledgeService,
)
from services.rule_engine_service import (
    RuleEngineService,
)


class KnowledgeFusionService:
    """
    Firma, ürün, muhasebe kuralı ve Tek Düzen Hesap Planı
    bilgilerini birleştirerek açıklanabilir muhasebe önerisi hazırlar.

    Bu servis kesin muhasebe kaydı oluşturmaz.
    Üretilen bütün sonuçlar mali müşavir onayına tabidir.
    """

    def __init__(self):
        self.account_service = AccountingKnowledgeService()
        self.company_service = CompanyProfileService()
        self.product_service = ProductKnowledgeService()
        self.rule_engine = RuleEngineService()

    def analyze(
        self,
        invoice_data: dict,
        company_id: str,
        document_type: str = "purchase_invoice",
    ) -> dict:
        """
        Fatura verisi ve firma profiline göre birleşik analiz üretir.
        """

        company = self.company_service.get_company_by_id(
            company_id
        )

        if not company:
            raise ValueError(
                f"Firma profili bulunamadı: {company_id}"
            )

        company_validation = (
            self.company_service.validate_company_profile(
                company_id
            )
        )

        if not company_validation["is_valid"]:
            raise ValueError(
                "Firma profili geçerli değil:\n"
                + "\n".join(
                    company_validation["errors"]
                )
            )

        raw_text = str(
            invoice_data.get("raw_text", "")
        )

        activity_type = company.get(
            "activity_type",
            "",
        )

        product_result = (
            self.product_service.suggest_usage(
                text=raw_text,
                activity_type=activity_type,
            )
        )

        usage = product_result.get("usage")

        facts = {
            "activity_type": activity_type,
            "document_type": document_type,
            "usage": usage,
        }

        rule_result = self.rule_engine.evaluate(facts)

        decision = self._build_decision(
            company=company,
            company_validation=company_validation,
            product_result=product_result,
            rule_result=rule_result,
            facts=facts,
        )

        return decision

    def _build_decision(
        self,
        company: dict,
        company_validation: dict,
        product_result: dict,
        rule_result: dict,
        facts: dict,
    ) -> dict:
        """
        Bütün bilgi kaynaklarını tek ve açıklanabilir bir sonuca dönüştürür.
        """

        warnings = list(
            company_validation.get(
                "warnings",
                [],
            )
        )

        conflicts = []

        product_account = product_result.get(
            "suggested_account"
        )

        rule_account = rule_result.get(
            "account_code"
        )

        if (
            product_account
            and rule_account
            and product_account != rule_account
        ):
            conflicts.append(
                "Ürün bilgi tabanı ile kural motoru "
                "farklı hesaplar önerdi."
            )

        selected_account_code = None
        decision_source = None

        if rule_result.get("matched"):
            selected_account_code = rule_account
            decision_source = "rule_engine"

        elif product_result.get("matched"):
            selected_account_code = product_account
            decision_source = "product_knowledge"

        if not selected_account_code:
            return self._build_uncertain_result(
                company=company,
                product_result=product_result,
                rule_result=rule_result,
                facts=facts,
                warnings=warnings,
                conflicts=conflicts,
            )

        account = self.account_service.get_account(
            selected_account_code
        )

        if not account:
            raise ValueError(
                "Önerilen hesap Tek Düzen bilgi "
                "tabanında bulunamadı: "
                f"{selected_account_code}"
            )

        confidence = self._calculate_confidence(
            product_result=product_result,
            rule_result=rule_result,
            conflicts=conflicts,
        )

        reasons = self._build_reasons(
            company=company,
            product_result=product_result,
            rule_result=rule_result,
            account=account,
        )

        if not account.get("verified", False):
            warnings.append(
                f"{selected_account_code} hesabının "
                "bilgi tabanı kaydı henüz resmî kaynak "
                "kontrolünden geçirilmemiştir."
            )

        if product_result.get(
            "requires_fixed_asset_validation",
            False,
        ):
            warnings.append(
                "Aktifleştirme, faydalı ömür ve "
                "amortisman şartları ayrıca kontrol edilmelidir."
            )

        if product_result.get(
            "requires_allocation",
            False,
        ):
            warnings.append(
                "Giderin üretim, hizmet, satış veya genel "
                "yönetim bölümleri arasında dağıtılması gerekebilir."
            )

        warnings.append(
            "Ürünün veya hizmetin gerçek kullanım amacı "
            "kullanıcı tarafından doğrulanmalıdır."
        )

        warnings.append(
            "Mali müşavir onayı olmadan kayıt "
            "kesinleştirilemez veya dış programa aktarılamaz."
        )

        return {
            "matched": True,
            "company_id": company.get("company_id"),
            "company_title": company.get("title"),
            "activity_type": company.get("activity_type"),
            "sector": company.get("sector"),
            "document_type": facts.get("document_type"),
            "product_matched": product_result.get(
                "matched",
                False,
            ),
            "product_id": self._get_product_value(
                product_result,
                "product_id",
            ),
            "product_name": self._get_product_value(
                product_result,
                "name",
            ),
            "matched_keywords": product_result.get(
                "matched_keywords",
                [],
            ),
            "detected_usage": product_result.get(
                "usage",
            ),
            "selected_account_code": account.get(
                "code"
            ),
            "selected_account_name": account.get(
                "name"
            ),
            "decision_source": decision_source,
            "confidence": confidence,
            "applied_rule_id": (
                rule_result.get(
                    "selected_rule",
                    {},
                ).get("rule_id")
                if rule_result.get("matched")
                else None
            ),
            "applied_rule_description": (
                rule_result.get(
                    "selected_rule",
                    {},
                ).get("description")
                if rule_result.get("matched")
                else None
            ),
            "matched_conditions": (
                rule_result.get(
                    "selected_rule",
                    {},
                ).get(
                    "matched_conditions",
                    [],
                )
                if rule_result.get("matched")
                else []
            ),
            "reasons": reasons,
            "warnings": self._unique_values(warnings),
            "conflicts": conflicts,
            "requires_user_confirmation": True,
            "can_create_final_voucher": False,
        }

    def _build_uncertain_result(
        self,
        company: dict,
        product_result: dict,
        rule_result: dict,
        facts: dict,
        warnings: list[str],
        conflicts: list[str],
    ) -> dict:
        """
        Yeterli bilgi bulunmadığında kesin hesap önermeyen sonuç üretir.
        """

        warnings.append(
            "Ürün veya hizmet yeterli güvenle sınıflandırılamadı."
        )

        warnings.append(
            "Kullanım amacı belirlenmeden muhasebe hesabı "
            "kesinleştirilmemelidir."
        )

        return {
            "matched": False,
            "company_id": company.get("company_id"),
            "company_title": company.get("title"),
            "activity_type": company.get("activity_type"),
            "sector": company.get("sector"),
            "document_type": facts.get("document_type"),
            "product_matched": product_result.get(
                "matched",
                False,
            ),
            "product_id": self._get_product_value(
                product_result,
                "product_id",
            ),
            "product_name": self._get_product_value(
                product_result,
                "name",
            ),
            "matched_keywords": product_result.get(
                "matched_keywords",
                [],
            ),
            "detected_usage": product_result.get(
                "usage",
            ),
            "selected_account_code": None,
            "selected_account_name": None,
            "decision_source": None,
            "confidence": 0,
            "applied_rule_id": None,
            "applied_rule_description": None,
            "matched_conditions": [],
            "reasons": [
                product_result.get(
                    "reason",
                    "Ürün bilgisi bulunamadı.",
                ),
                rule_result.get(
                    "reason",
                    "Muhasebe kuralı eşleşmedi.",
                ),
            ],
            "warnings": self._unique_values(warnings),
            "conflicts": conflicts,
            "requires_user_confirmation": True,
            "can_create_final_voucher": False,
        }

    def _calculate_confidence(
        self,
        product_result: dict,
        rule_result: dict,
        conflicts: list[str],
    ) -> int:
        """
        Ürün ve kural güven oranlarını kontrollü şekilde birleştirir.
        """

        product_confidence = int(
            product_result.get(
                "confidence",
                0,
            )
        )

        rule_confidence = int(
            rule_result.get(
                "confidence",
                0,
            )
        )

        if product_confidence and rule_confidence:
            confidence = min(
                product_confidence,
                rule_confidence,
            )

        else:
            confidence = max(
                product_confidence,
                rule_confidence,
            )

        if conflicts:
            confidence -= 25

        if not product_result.get(
            "verified",
            False,
        ):
            confidence -= 5

        return max(
            0,
            min(confidence, 100),
        )

    def _build_reasons(
        self,
        company: dict,
        product_result: dict,
        rule_result: dict,
        account: dict,
    ) -> list[str]:
        """
        Kararın hangi kaynaklara göre verildiğini açıklar.
        """

        reasons = [
            (
                "Firma profili: "
                f"{company.get('title', '-')}, "
                f"faaliyet türü: "
                f"{company.get('activity_type', '-')}."
            )
        ]

        if product_result.get("matched"):
            product = product_result.get(
                "product",
                {},
            )

            reasons.append(
                "Ürün veya hizmet eşleşmesi: "
                f"{product.get('name', '-')}."
            )

            reasons.append(
                "Ürün bilgi tabanı gerekçesi: "
                f"{product_result.get('reason', '-')}"
            )

        if rule_result.get("matched"):
            reasons.append(
                "Kural motoru gerekçesi: "
                f"{rule_result.get('reason', '-')}"
            )

        reasons.append(
            "Tek Düzen hesap bilgisi: "
            f"{account.get('code')} "
            f"{account.get('name')}."
        )

        return reasons

    def _get_product_value(
        self,
        product_result: dict,
        key: str,
    ):
        product = product_result.get("product")

        if not product:
            return None

        return product.get(key)

    def _unique_values(
        self,
        values: list[str],
    ) -> list[str]:
        """
        Aynı uyarının birden fazla kez görünmesini engeller.
        """

        unique_values = []

        for value in values:
            if value and value not in unique_values:
                unique_values.append(value)

        return unique_values