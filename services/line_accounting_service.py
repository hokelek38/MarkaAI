from services.accounting_knowledge_service import (
    AccountingKnowledgeService,
)

from services.line_usage_service import LineUsageService


class LineAccountingService:
    """
    Fatura kalemlerini firma profiline ve açıklamasına göre
    ayrı ayrı muhasebe hesaplarına yönlendirir.

    Üretilen sonuç öneridir ve mali müşavir onayı gerektirir.
    """

    FIXED_ASSET_KEYWORDS = [
        "bilgisayar",
        "laptop",
        "notebook",
        "yazıcı",
        "printer",
        "monitör",
        "telefon cihazı",
        "masa",
        "koltuk",
        "mobilya",
        "makine",
        "tezgah",
        "ekipman",
        "klima",
        "kamera",
        "server",
        "sunucu",
        "demirbaş",
    ]

    PRODUCTION_MATERIAL_KEYWORDS = [
        "mdf",
        "suntalam",
        "sunta",
        "levha",
        "kereste",
        "ahşap",
        "kumaş",
        "sünger",
        "boya",
        "vernik",
        "tutkal",
        "yapıştırıcı",
        "vida",
        "civata",
        "profil",
        "sac",
        "metal",
        "plastik",
        "pvc bant",
        "kenar bant",
        "hammadde",
        "ham madde",
        "yarı mamul",
        "malzeme",
    ]

    SELLING_EXPENSE_KEYWORDS = [
        "reklam",
        "ilan",
        "pazarlama",
        "promosyon",
        "fuar",
        "satış komisyonu",
        "sosyal medya reklam",
    ]

    ADMINISTRATIVE_EXPENSE_KEYWORDS = [
        "muhasebe",
        "mali müşavir",
        "danışmanlık",
        "hukuk",
        "kırtasiye",
        "ofis malzemesi",
        "telefon",
        "internet",
        "elektrik",
        "doğalgaz",
        "su faturası",
        "kira",
        "temizlik",
        "noter",
        "aidat",
        "yazılım lisansı",
        "abonelik",
    ]

    SERVICE_PRODUCTION_KEYWORDS = [
        "işçilik",
        "montaj",
        "fason",
        "bakım hizmeti",
        "onarım hizmeti",
        "teknik servis",
        "proje hizmeti",
        "üretim hizmeti",
    ]

    ACCOUNT_NAMES = {
        "150": "İlk Madde ve Malzeme",
        "153": "Ticari Mallar",
        "255": "Demirbaşlar",
        "740": "Hizmet Üretim Maliyeti",
        "760": "Pazarlama Satış ve Dağıtım Giderleri",
        "770": "Genel Yönetim Giderleri",
    }

    def __init__(self):
        self.knowledge_service = (
            AccountingKnowledgeService()
        )
        self.line_usage_service = (
            LineUsageService()
        )

    def classify_lines(
        self,
        line_items: list[dict],
        company: dict,
    ) -> list[dict]:
        """
        Bütün fatura kalemlerini ayrı ayrı sınıflandırır.
        """

        results = []

        for line_item in line_items:
            result = self.classify_line(
                line_item=line_item,
                company=company,
            )

            results.append(result)

        return results

    def classify_line(
        self,
        *,
        line_item: dict,
        company: dict,
    ) -> dict:
        """
        Tek fatura kaleminin kullanım amacını
        belirler ve yalnızca güvenli durumda
        muhasebe hesabı önerir.
        """

        usage_result = (
            self.line_usage_service.classify(
                line_item=line_item,
                company=company,
            )
        )

        configured_account_code = str(
            usage_result.get(
                "configured_account_code",
                "",
            )
        ).strip()

        usage_posting_allowed = bool(
            usage_result.get(
                "posting_allowed",
                False,
            )
        )

        account_code = (
            configured_account_code
            if usage_posting_allowed
            else ""
        )

        final_posting_allowed = bool(
            usage_posting_allowed
            and account_code
        )

        if account_code:
            account_name = (
                self._get_account_name(
                    account_code
                )
            )
        else:
            account_name = (
                "Hesap Seçilmedi"
            )

        warnings = list(
            usage_result.get(
                "warnings",
                [],
            )
        )

        if (
            usage_posting_allowed
            and not account_code
        ):
            warnings.append(
                "Kullanım amacı belirlendi ancak "
                "firma profilinde uygun muhasebe "
                "hesabı tanımlı değil."
            )

        result = dict(line_item)

        result.update({
            "account_code": account_code,
            "account_name": account_name,

            "usage": usage_result.get(
                "usage",
                "",
            ),
            "usage_name": usage_result.get(
                "usage_name",
                "Belirlenemedi",
            ),
            "usage_status": usage_result.get(
                "status",
                "unresolved",
            ),
            "account_purpose": (
                usage_result.get(
                    "account_purpose",
                    "",
                )
            ),

            "confidence": int(
                usage_result.get(
                    "confidence",
                    0,
                )
                or 0
            ),

            "matched_keywords": list(
                usage_result.get(
                    "matched_signals",
                    [],
                )
            ),

            "reason": usage_result.get(
                "reason",
                "",
            ),

            "usage_candidates": list(
                usage_result.get(
                    "candidates",
                    [],
                )
            ),

            "posting_allowed": (
                final_posting_allowed
            ),

            "requires_user_confirmation": (
                usage_result.get(
                    "requires_user_confirmation",
                    True,
                )
                or not final_posting_allowed
            ),

            "warnings": list(
                dict.fromkeys(
                    warnings
                )
            ),
        })

        return result

    def _detect_usage(
        self,
        *,
        text: str,
        company: dict,
    ) -> dict:
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
                    "Birden fazla dönemde kullanılabilecek "
                    "kıymet ifadeleri bulundu. Aktifleştirme "
                    "şartları kullanıcı tarafından kontrol edilmelidir."
                ),
            }

        selling_matches = self._find_matches(
            text,
            self.SELLING_EXPENSE_KEYWORDS,
        )

        if selling_matches:
            return {
                "usage": "selling",
                "confidence": 88,
                "matched_keywords": selling_matches,
                "reason": (
                    "Satış, pazarlama veya tanıtım faaliyetiyle "
                    "ilişkili ifadeler bulundu."
                ),
            }

        administrative_matches = self._find_matches(
            text,
            self.ADMINISTRATIVE_EXPENSE_KEYWORDS,
        )

        if administrative_matches:
            return {
                "usage": "administrative",
                "confidence": 87,
                "matched_keywords": administrative_matches,
                "reason": (
                    "Genel yönetim faaliyetiyle ilişkili "
                    "ifadeler bulundu."
                ),
            }

        activity_types = list(
            company.get(
                "activity_types",
                [],
            )
        )

        primary_activity = company.get(
            "primary_activity_type",
            company.get(
                "activity_type",
                "",
            ),
        )

        if (
            primary_activity
            and primary_activity not in activity_types
        ):
            activity_types.insert(
                0,
                primary_activity,
            )

        production_matches = self._find_matches(
            text,
            self.PRODUCTION_MATERIAL_KEYWORDS,
        )

        if (
            "manufacturing" in activity_types
            and production_matches
        ):
            return {
                "usage": "production",
                "confidence": 94,
                "matched_keywords": production_matches,
                "reason": (
                    "Firma imalat işletmesidir ve kalem "
                    "açıklamasında üretim malzemesi ifadeleri bulundu."
                ),
            }

        service_matches = self._find_matches(
            text,
            self.SERVICE_PRODUCTION_KEYWORDS,
        )

        if (
            "service" in activity_types
            and service_matches
        ):
            return {
                "usage": "service_production",
                "confidence": 88,
                "matched_keywords": service_matches,
                "reason": (
                    "Firma hizmet işletmesidir ve kalem "
                    "hizmet üretimiyle ilişkili görünmektedir."
                ),
            }

        if "trading" in activity_types:
            return {
                "usage": "resale",
                "confidence": 75,
                "matched_keywords": [],
                "reason": (
                    "Firma ticaret işletmesidir. Kalemin yeniden "
                    "satılmak üzere alındığı varsayılmıştır."
                ),
            }

        if "manufacturing" in activity_types:
            return {
                "usage": "production",
                "confidence": 55,
                "matched_keywords": [],
                "reason": (
                    "Firma imalat işletmesidir ancak kalemin üretimde "
                    "kullanım amacı açıklamadan kesinleştirilememiştir."
                ),
            }

        if "service" in activity_types:
            return {
                "usage": "administrative",
                "confidence": 45,
                "matched_keywords": [],
                "reason": (
                    "Firma hizmet işletmesidir ancak giderin kullanım "
                    "amacı açıklamadan kesinleştirilememiştir."
                ),
            }

        return {
            "usage": "administrative",
            "confidence": 30,
            "matched_keywords": [],
            "reason": (
                "Kalemin kullanım amacı belirlenemedi. "
                "Geçici olarak genel yönetim gideri önerildi."
            ),
        }

    def _select_account_code(
        self,
        *,
        company: dict,
        usage: str,
    ) -> str:
        purpose_map = {
            "production": "raw_material",
            "resale": "trade_goods",
            "fixed_asset": "fixed_asset",
            "service_production": (
                "direct_service_cost"
            ),
            "selling": "selling_expense",
            "administrative": (
                "administrative_expense"
            ),
        }

        fallback_codes = {
            "production": "150",
            "resale": "153",
            "fixed_asset": "255",
            "service_production": "740",
            "selling": "760",
            "administrative": "770",
        }

        purpose = purpose_map.get(
            usage,
            "administrative_expense",
        )

        company_accounts = company.get(
            "default_purchase_accounts",
            {},
        )

        return str(
            company_accounts.get(
                purpose,
                fallback_codes.get(
                    usage,
                    "770",
                ),
            )
        )

    def _get_account_name(
        self,
        account_code: str,
    ) -> str:
        account = self.knowledge_service.get_account(
            account_code
        )

        if account:
            return account.get(
                "name",
                self.ACCOUNT_NAMES.get(
                    account_code,
                    "Muhasebe Hesabı",
                ),
            )

        return self.ACCOUNT_NAMES.get(
            account_code,
            "Muhasebe Hesabı",
        )

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
