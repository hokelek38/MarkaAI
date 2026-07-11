from services.accounting_knowledge_service import (
    AccountingKnowledgeService,
)
from services.company_profile_service import (
    CompanyProfileService,
)
from services.rule_engine_service import (
    RuleEngineService,
)


class AccountingService:
    """
    Fatura içeriği, firma profili ve muhasebe kurallarına göre
    gerekçeli hesap önerisi üretir.

    Bu servis kesin muhasebe kaydı oluşturmaz.
    Bütün öneriler mali müşavir kontrolü ve onayına tabidir.
    """

    MATERIAL_KEYWORDS = [
        "ahşap",
        "kereste",
        "mdf",
        "sunta",
        "kontrplak",
        "kumaş",
        "sünger",
        "boya",
        "vernik",
        "tutkal",
        "hammadde",
        "ham madde",
        "malzeme",
        "torna ayak",
        "mobilya ayağı",
    ]

    TRADE_GOODS_KEYWORDS = [
        "ticari mal",
        "satış ürünü",
        "ürün alımı",
        "satılmak üzere",
        "yeniden satış",
    ]

    FIXED_ASSET_KEYWORDS = [
        "bilgisayar",
        "laptop",
        "masaüstü bilgisayar",
        "yazıcı",
        "fotokopi makinesi",
        "ofis mobilyası",
        "ofis koltuğu",
        "çalışma masası",
        "makine",
        "cihaz",
        "demirbaş",
        "klima",
    ]

    SERVICE_PRODUCTION_KEYWORDS = [
        "taşeron hizmet",
        "proje hizmeti",
        "üretim hizmeti",
        "montaj hizmeti",
        "işçilik hizmeti",
        "bakım hizmeti",
        "yazılım geliştirme hizmeti",
    ]

    ADMINISTRATIVE_KEYWORDS = [
        "telefon",
        "internet",
        "elektrik",
        "su faturası",
        "doğalgaz",
        "kırtasiye",
        "temizlik",
        "muhasebe hizmeti",
        "hukuk hizmeti",
        "danışmanlık",
        "büro gideri",
    ]

    SELLING_KEYWORDS = [
        "reklam",
        "tanıtım",
        "pazarlama",
        "satış komisyonu",
        "dağıtım",
        "kargo",
        "nakliye",
    ]

    def __init__(self):
        self.knowledge_service = AccountingKnowledgeService()
        self.company_profile_service = CompanyProfileService()
        self.rule_engine = RuleEngineService()

    def suggest_accounts(
        self,
        invoice_data: dict,
        company_id: str = "demo_manufacturing",
    ) -> dict:
        """
        Firma profiline ve faturaya göre muhasebe fişi önerisi üretir.
        """

        company = self.company_profile_service.get_company_by_id(
            company_id
        )

        if not company:
            raise ValueError(
                f"Firma profili bulunamadı: {company_id}"
            )

        profile_validation = (
            self.company_profile_service.validate_company_profile(
                company_id
            )
        )

        if not profile_validation["is_valid"]:
            raise ValueError(
                "Firma profili geçerli değil:\n"
                + "\n".join(profile_validation["errors"])
            )

        raw_text = str(
            invoice_data.get("raw_text", "")
        ).casefold()

        usage_result = self._infer_usage(
            text=raw_text,
            company=company,
        )

        facts = {
            "activity_type": company.get(
                "activity_type",
                "",
            ),
            "document_type": "purchase_invoice",
            "usage": usage_result["usage"],
        }

        rule_result = self.rule_engine.evaluate(facts)

        if rule_result["matched"]:
            purchase_account_code = rule_result[
                "account_code"
            ]

            confidence = min(
                int(rule_result.get("confidence", 0)),
                int(usage_result.get("confidence", 0)),
            )

            reason = (
                f"{usage_result['reason']} "
                f"Uygulanan kural: "
                f"{rule_result['selected_rule']['rule_id']}. "
                f"{rule_result['reason']}"
            )

        else:
            purchase_account_code = self._fallback_account(
                company=company,
                usage=usage_result["usage"],
            )

            confidence = min(
                int(usage_result.get("confidence", 0)),
                35,
            )

            reason = (
                f"{usage_result['reason']} "
                "Kural motorunda tam eşleşme bulunamadı. "
                "Geçici hesap önerisi oluşturuldu ve kullanıcı "
                "kontrolü zorunludur."
            )

        debit_entries = [
            self._create_entry(
                account_code=purchase_account_code,
                amount=invoice_data.get(
                    "subtotal",
                    "-",
                ),
            )
        ]

        vat_amount = invoice_data.get(
            "vat_amount",
            "-",
        )

        if self._has_valid_amount(vat_amount):
            debit_entries.append(
                self._create_entry(
                    account_code="191",
                    amount=vat_amount,
                )
            )

        payable_amount = invoice_data.get(
            "payable_amount",
            invoice_data.get(
                "total_amount",
                "-",
            ),
        )

        credit_entries = [
            self._create_entry(
                account_code="320",
                amount=payable_amount,
            )
        ]

        warnings = self._build_warnings(
            invoice_data=invoice_data,
            company=company,
            account_code=purchase_account_code,
            usage_result=usage_result,
            profile_warnings=profile_validation[
                "warnings"
            ],
            rule_matched=rule_result["matched"],
        )

        selected_rule = rule_result.get(
            "selected_rule"
        )

        return {
            "company_id": company_id,
            "company_title": company.get(
                "title",
                "-",
            ),
            "activity_type": company.get(
                "activity_type",
                "-",
            ),
            "sector": company.get(
                "sector",
                "-",
            ),
            "document_type": "purchase_invoice",
            "detected_usage": usage_result["usage"],
            "usage_reason": usage_result["reason"],
            "matched_keywords": usage_result[
                "matched_keywords"
            ],
            "debit_entries": debit_entries,
            "credit_entries": credit_entries,
            "reason": reason,
            "confidence": confidence,
            "rule_matched": rule_result["matched"],
            "applied_rule_id": (
                selected_rule.get("rule_id")
                if selected_rule
                else None
            ),
            "applied_rule_description": (
                selected_rule.get("description")
                if selected_rule
                else None
            ),
            "matched_conditions": (
                selected_rule.get(
                    "matched_conditions",
                    [],
                )
                if selected_rule
                else []
            ),
            "alternative_accounts": (
                self._get_alternatives(
                    purchase_account_code
                )
            ),
            "warnings": warnings,
            "requires_user_confirmation": True,
            "knowledge_base_version": (
                self._get_knowledge_version()
            ),
            "rule_base_version": (
                self.rule_engine
                .get_metadata()
                .get("version", "bilinmiyor")
            ),
        }

    def _infer_usage(
        self,
        text: str,
        company: dict,
    ) -> dict:
        """
        Firma türü ve fatura metnine göre alışın kullanım amacını belirler.

        Hesabı bu metot seçmez.
        Sadece Rule Engine için kullanım amacı üretir.
        """

        company_id = company.get(
            "company_id",
            "",
        )

        company_rules = (
            self.company_profile_service
            .find_matching_rules(
                company_id,
                text,
            )
        )

        if company_rules:
            best_rule = max(
                company_rules,
                key=lambda rule: rule.get(
                    "confidence",
                    0,
                ),
            )

            usage = best_rule.get(
                "usage_purpose",
                "",
            )

            matched_keywords = best_rule.get(
                "matched_keywords",
                [],
            )

            if usage:
                return {
                    "usage": usage,
                    "confidence": int(
                        best_rule.get(
                            "confidence",
                            75,
                        )
                    ),
                    "matched_keywords": matched_keywords,
                    "reason": (
                        "Firmaya özel sınıflandırma kuralı "
                        "eşleşti. Bulunan ifadeler: "
                        f"{', '.join(matched_keywords)}."
                    ),
                }

        fixed_asset_matches = self._find_matches(
            text,
            self.FIXED_ASSET_KEYWORDS,
        )

        if fixed_asset_matches:
            return {
                "usage": "fixed_asset",
                "confidence": 72,
                "matched_keywords": fixed_asset_matches,
                "reason": (
                    "İşletmede birden fazla dönemde "
                    "kullanılabilecek kıymet ifadeleri bulundu: "
                    f"{', '.join(fixed_asset_matches)}. "
                    "Aktifleştirme ve amortisman şartları "
                    "ayrıca kontrol edilmelidir."
                ),
            }

        administrative_matches = self._find_matches(
            text,
            self.ADMINISTRATIVE_KEYWORDS,
        )

        if administrative_matches:
            return {
                "usage": "administrative",
                "confidence": 74,
                "matched_keywords": administrative_matches,
                "reason": (
                    "Genel yönetim faaliyetiyle ilişkili "
                    "ifadeler bulundu: "
                    f"{', '.join(administrative_matches)}."
                ),
            }

        selling_matches = self._find_matches(
            text,
            self.SELLING_KEYWORDS,
        )

        if selling_matches:
            return {
                "usage": "selling",
                "confidence": 75,
                "matched_keywords": selling_matches,
                "reason": (
                    "Pazarlama, satış veya dağıtım "
                    "faaliyetiyle ilişkili ifadeler bulundu: "
                    f"{', '.join(selling_matches)}."
                ),
            }

        activity_type = company.get(
            "activity_type",
            "",
        )

        if activity_type == "manufacturing":
            material_matches = self._find_matches(
                text,
                self.MATERIAL_KEYWORDS,
            )

            if material_matches:
                return {
                    "usage": "production",
                    "confidence": 92,
                    "matched_keywords": material_matches,
                    "reason": (
                        "Firma imalat işletmesidir ve üretimde "
                        "kullanılabilecek malzeme ifadeleri "
                        "bulundu: "
                        f"{', '.join(material_matches)}."
                    ),
                }

        if activity_type == "trading":
            return {
                "usage": "resale",
                "confidence": 70,
                "matched_keywords": [],
                "reason": (
                    "Firma alım-satım işletmesidir. Alınan "
                    "malın yeniden satış amacıyla edinildiği "
                    "varsayılmıştır. Kullanım amacı ayrıca "
                    "doğrulanmalıdır."
                ),
            }

        if activity_type == "service":
            service_matches = self._find_matches(
                text,
                self.SERVICE_PRODUCTION_KEYWORDS,
            )

            if service_matches:
                return {
                    "usage": "service_production",
                    "confidence": 84,
                    "matched_keywords": service_matches,
                    "reason": (
                        "Firma hizmet işletmesidir ve hizmet "
                        "üretimiyle doğrudan ilişkili ifadeler "
                        "bulundu: "
                        f"{', '.join(service_matches)}."
                    ),
                }

        return {
            "usage": "administrative",
            "confidence": 30,
            "matched_keywords": [],
            "reason": (
                "Alışın kullanım amacı kesin olarak "
                "belirlenemedi. Geçici olarak genel yönetim "
                "amacı kabul edilmiştir."
            ),
        }

    def _fallback_account(
        self,
        company: dict,
        usage: str,
    ) -> str:
        """
        Kural motorunda eşleşme olmadığında geçici hesap seçer.
        """

        purpose_map = {
            "production": "raw_material",
            "resale": "trade_goods",
            "fixed_asset": "fixed_asset",
            "service_production": (
                "direct_service_cost"
            ),
            "administrative": (
                "administrative_expense"
            ),
            "selling": "selling_expense",
        }

        fallback_codes = {
            "production": "150",
            "resale": "153",
            "fixed_asset": "255",
            "service_production": "740",
            "administrative": "770",
            "selling": "760",
        }

        purpose = purpose_map.get(
            usage,
            "administrative_expense",
        )

        account_code = company.get(
            "default_purchase_accounts",
            {},
        ).get(
            purpose,
            fallback_codes.get(
                usage,
                "770",
            ),
        )

        if not self.knowledge_service.account_exists(
            account_code
        ):
            raise ValueError(
                "Geçici olarak önerilen hesap bilgi "
                "tabanında bulunamadı: "
                f"{account_code}"
            )

        return account_code

    def _create_entry(
        self,
        account_code: str,
        amount,
    ) -> dict:
        """
        Tek Düzen bilgi tabanından muhasebe satırı oluşturur.
        """

        account = self.knowledge_service.get_account(
            account_code
        )

        if not account:
            raise ValueError(
                "Önerilen hesap bilgi tabanında "
                f"bulunamadı: {account_code}"
            )

        return {
            "account_code": account["code"],
            "account_name": account["name"],
            "amount": amount,
            "verified": account.get(
                "verified",
                False,
            ),
            "normal_balance": account.get(
                "normal_balance",
                "",
            ),
            "requires_user_confirmation": (
                account.get(
                    "requires_user_confirmation",
                    True,
                )
            ),
        }

    def _get_alternatives(
        self,
        account_code: str,
    ) -> list[dict]:
        alternatives = (
            self.knowledge_service
            .get_alternative_accounts(
                account_code
            )
        )

        return [
            {
                "account_code": account.get(
                    "code",
                    "",
                ),
                "account_name": account.get(
                    "name",
                    "",
                ),
                "usage": account.get(
                    "usage",
                    "",
                ),
            }
            for account in alternatives
        ]

    def _build_warnings(
        self,
        invoice_data: dict,
        company: dict,
        account_code: str,
        usage_result: dict,
        profile_warnings: list[str],
        rule_matched: bool,
    ) -> list[str]:
        warnings = list(profile_warnings)

        if invoice_data.get("invoice_number") in {
            None,
            "",
            "-",
        }:
            warnings.append(
                "Fatura numarası okunamadı."
            )

        if invoice_data.get("invoice_date") in {
            None,
            "",
            "-",
        }:
            warnings.append(
                "Fatura tarihi okunamadı."
            )

        if invoice_data.get(
            "seller_tax_number"
        ) in {
            None,
            "",
            "-",
        }:
            warnings.append(
                "Satıcı VKN/TCKN bilgisi okunamadı."
            )

        if not rule_matched:
            warnings.append(
                "Kural motorunda tam eşleşme "
                "bulunamadı."
            )

        if usage_result["confidence"] < 60:
            warnings.append(
                "Alışın kullanım amacı düşük güvenle "
                "belirlendi."
            )

        if not self.knowledge_service.is_account_verified(
            account_code
        ):
            warnings.append(
                f"{account_code} hesabının bilgi tabanı "
                "kaydı henüz resmî kaynak kontrolünden "
                "geçirilmemiştir."
            )

        warnings.append(
            f"Öneri {company.get('title', 'firma')} "
            "profiline göre hazırlanmıştır."
        )

        warnings.append(
            "Ürünün veya hizmetin gerçek kullanım "
            "amacı kullanıcı tarafından doğrulanmalıdır."
        )

        warnings.append(
            "Mali müşavir onayı olmadan fiş "
            "kesinleştirilemez veya dış programa "
            "aktarılamaz."
        )

        return warnings

    def _find_matches(
        self,
        text: str,
        keywords: list[str],
    ) -> list[str]:
        return [
            keyword
            for keyword in keywords
            if keyword.casefold() in text
        ]

    def _has_valid_amount(
        self,
        amount,
    ) -> bool:
        if amount is None:
            return False

        normalized_amount = str(amount).strip()

        return normalized_amount not in {
            "",
            "-",
            "0",
            "0,00",
            "0,00 TL",
        }

    def _get_knowledge_version(self) -> str:
        metadata = self.knowledge_service.get_metadata()

        return metadata.get(
            "version",
            "bilinmiyor",
        )