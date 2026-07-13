import re
import unicodedata


class LineUsageService:
    """
    Fatura kaleminin işletmedeki gerçek kullanım amacını belirler.

    Firma türü tek başına kullanım amacı veya
    muhasebe hesabı seçmek için yeterli değildir.
    """

    USAGE_NAMES = {
        "production_material": (
            "Üretim İlk Madde / Malzemesi"
        ),
        "resale_goods": (
            "Yeniden Satılacak Ticari Mal"
        ),
        "service_production": (
            "Hizmet Üretiminde Doğrudan Kullanım"
        ),
        "selling_expense": (
            "Pazarlama / Satış / Dağıtım"
        ),
        "administrative_expense": (
            "Genel Yönetim"
        ),
        "fixed_asset": (
            "Duran Varlık Adayı"
        ),
    }

    USAGE_ALIASES = {
        "production": "production_material",
        "production_material": (
            "production_material"
        ),
        "raw_material": "production_material",
        "hammadde": "production_material",

        "resale": "resale_goods",
        "resale_goods": "resale_goods",
        "trade_goods": "resale_goods",
        "ticari_mal": "resale_goods",

        "service_production": (
            "service_production"
        ),
        "direct_service_cost": (
            "service_production"
        ),

        "selling": "selling_expense",
        "selling_expense": (
            "selling_expense"
        ),

        "administrative": (
            "administrative_expense"
        ),
        "administrative_expense": (
            "administrative_expense"
        ),

        "fixed_asset": "fixed_asset",
        "duran_varlik": "fixed_asset",
        "demirbas": "fixed_asset",
    }

    PURPOSE_MAP = {
        "production_material": "raw_material",
        "resale_goods": "trade_goods",
        "service_production": (
            "direct_service_cost"
        ),
        "selling_expense": (
            "selling_expense"
        ),
        "administrative_expense": (
            "administrative_expense"
        ),
        "fixed_asset": "fixed_asset",
    }

    CORE_ACTIVITY_MAP = {
        "production_material": "manufacturing",
        "resale_goods": "trading",
        "service_production": "service",
    }

    STRONG_PHRASES = {
        "production_material": [
            "uretimde kullanilmak uzere",
            "imalatta kullanilmak uzere",
            "hammadde olarak",
            "uretimin girdisi",
            "uretim malzemesi",
        ],
        "resale_goods": [
            "satilmak uzere",
            "yeniden satilmak uzere",
            "ticari mal olarak",
            "stok mali",
        ],
        "service_production": [
            "hizmet uretiminde",
            "musteri projesinde",
            (
                "verilen hizmette "
                "kullanilmak uzere"
            ),
            "proje icin dis hizmet",
            "fason hizmet",
        ],
        "selling_expense": [
            "reklam hizmeti",
            "pazarlama hizmeti",
            "satis komisyonu",
            "sosyal medya reklami",
        ],
        "administrative_expense": [
            "muhasebe hizmeti",
            "mali musavirlik hizmeti",
            "hukuk danismanligi",
            "genel yonetim",
            "ofis kullanimi",
        ],
        "fixed_asset": [
            "duran varlik",
            "demirbas olarak",
            "makine yatirimi",
            (
                "ofiste kullanilacak "
                "bilgisayar"
            ),
        ],
    }

    KEYWORDS = {
        "production_material": [
            "mdf",
            "suntalam",
            "sunta",
            "kereste",
            "ahsap",
            "kumas",
            "sunger",
            "vernik",
            "tutkal",
            "yapistirici",
            "vida",
            "civata",
            "profil",
            "sac",
            "hammadde",
            "ham madde",
            "yari mamul",
        ],
        "resale_goods": [
            "ticari mal",
            "stok mali",
            "yeniden satis",
            "satilacak urun",
        ],
        "service_production": [
            "iscilik",
            "montaj",
            "fason",
            "proje hizmeti",
            "teknik servis",
            "dis hizmet",
        ],
        "selling_expense": [
            "reklam",
            "ilan",
            "pazarlama",
            "promosyon",
            "fuar",
            "satis komisyonu",
        ],
        "administrative_expense": [
            "muhasebe",
            "mali musavir",
            "hukuk",
            "noter",
            "kirtasiye",
            "ofis malzemesi",
            "yonetim",
            "aidat",
        ],
        "fixed_asset": [
            "bilgisayar",
            "laptop",
            "notebook",
            "yazici",
            "monitor",
            "makine",
            "tezgah",
            "klima",
            "kamera",
            "server",
            "sunucu",
            "demirbas",
        ],
    }

    def classify(
        self,
        *,
        line_item: dict,
        company: dict,
    ) -> dict:
        """
        Tek fatura kaleminin kullanım amacını
        belirler.
        """

        text = self._normalize_text(
            line_item.get(
                "description",
                "",
            )
        )

        explicit_usage = (
            self._get_explicit_usage(
                line_item
            )
        )

        if explicit_usage:
            return self._result(
                company=company,
                status="resolved",
                usage=explicit_usage,
                confidence=100,
                source="explicit_usage",
                matched_signals=[
                    "Açık kullanım amacı"
                ],
                candidates=[],
                posting_allowed=(
                    explicit_usage
                    != "fixed_asset"
                ),
                requires_confirmation=(
                    explicit_usage
                    == "fixed_asset"
                ),
                reason=(
                    "Kullanım amacı belge veya "
                    "kullanıcı tarafından açıkça "
                    "belirtildi."
                ),
            )

        company_rule = (
            self._match_company_rule(
                text=text,
                company=company,
            )
        )

        if company_rule:
            usage = company_rule["usage"]

            return self._result(
                company=company,
                status=(
                    "needs_confirmation"
                    if usage == "fixed_asset"
                    else "resolved"
                ),
                usage=usage,
                confidence=company_rule[
                    "confidence"
                ],
                source="company_rule",
                matched_signals=(
                    company_rule[
                        "matched_signals"
                    ]
                ),
                candidates=[],
                posting_allowed=(
                    usage != "fixed_asset"
                ),
                requires_confirmation=(
                    usage == "fixed_asset"
                    or company_rule[
                        "confidence"
                    ] < 90
                ),
                reason=(
                    "Firmaya özel sınıflandırma "
                    "kuralı eşleşti."
                ),
                account_code=(
                    company_rule.get(
                        "account_code",
                        "",
                    )
                ),
            )

        if not text:
            return self._unresolved(
                company,
                "Kalem açıklaması boş.",
            )

        candidates = (
            self._score_candidates(
                text=text,
                company=company,
            )
        )

        if not candidates:
            return self._unresolved(
                company,
                (
                    "Kullanım amacını gösterecek "
                    "yeterli kanıt bulunamadı."
                ),
            )

        candidates.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        top = candidates[0]

        second = (
            candidates[1]
            if len(candidates) > 1
            else None
        )

        if top["score"] < 75:
            return self._result(
                company=company,
                status="unresolved",
                usage="",
                confidence=top["score"],
                source="keyword_analysis",
                matched_signals=(
                    top["matched_signals"]
                ),
                candidates=candidates[:3],
                posting_allowed=False,
                requires_confirmation=True,
                reason=(
                    "En güçlü aday yeterli güven "
                    "seviyesine ulaşmadı."
                ),
            )

        if (
            second
            and (
                top["score"]
                - second["score"]
            ) < 15
        ):
            return self._result(
                company=company,
                status="ambiguous",
                usage="",
                confidence=top["score"],
                source="keyword_analysis",
                matched_signals=(
                    top["matched_signals"]
                ),
                candidates=candidates[:3],
                posting_allowed=False,
                requires_confirmation=True,
                reason=(
                    "Birden fazla kullanım amacı "
                    "birbirine yakın güçte "
                    "bulundu."
                ),
            )

        if (
            self._is_mixed_company(
                company
            )
            and top["usage"]
            in self.CORE_ACTIVITY_MAP
            and not top[
                "explicit_purpose"
            ]
        ):
            return self._result(
                company=company,
                status="ambiguous",
                usage="",
                confidence=top["score"],
                source="mixed_company_guard",
                matched_signals=(
                    top["matched_signals"]
                ),
                candidates=candidates[:3],
                posting_allowed=False,
                requires_confirmation=True,
                reason=(
                    "Firma karma faaliyetlidir. "
                    "Kalemin üretim, satış veya "
                    "hizmet amacı açıkça "
                    "belirtilmemiştir."
                ),
            )

        if top["usage"] == "fixed_asset":
            return self._result(
                company=company,
                status="needs_confirmation",
                usage="fixed_asset",
                confidence=top["score"],
                source="keyword_analysis",
                matched_signals=(
                    top["matched_signals"]
                ),
                candidates=candidates[:3],
                posting_allowed=False,
                requires_confirmation=True,
                reason=(
                    "Kalem duran varlık adayıdır. "
                    "Hesap grubu kullanıcı "
                    "tarafından doğrulanmalıdır."
                ),
            )

        return self._result(
            company=company,
            status="resolved",
            usage=top["usage"],
            confidence=top["score"],
            source="keyword_analysis",
            matched_signals=(
                top["matched_signals"]
            ),
            candidates=candidates[:3],
            posting_allowed=True,
            requires_confirmation=(
                top["score"] < 90
            ),
            reason=(
                "Kalem açıklaması ve firma "
                "faaliyetleri birlikte "
                "değerlendirildi."
            ),
        )

    def _score_candidates(
        self,
        *,
        text: str,
        company: dict,
    ) -> list[dict]:
        activities = set(
            company.get(
                "activity_types",
                [],
            )
            or []
        )

        primary = str(
            company.get(
                "primary_activity_type",
                company.get(
                    "activity_type",
                    "",
                ),
            )
        ).strip()

        if primary:
            activities.add(primary)

        candidates = []

        for usage in self.USAGE_NAMES:
            score = 0
            signals = []
            explicit_purpose = False

            phrase_matches = (
                self._find_matches(
                    text,
                    self.STRONG_PHRASES.get(
                        usage,
                        [],
                    ),
                )
            )

            if phrase_matches:
                score += 90
                signals.extend(
                    phrase_matches
                )
                explicit_purpose = True

            keyword_matches = (
                self._find_matches(
                    text,
                    self.KEYWORDS.get(
                        usage,
                        [],
                    ),
                )
            )

            if keyword_matches:
                if usage in {
                    "selling_expense",
                    "administrative_expense",
                }:
                    score += 82

                elif usage == "fixed_asset":
                    score += 78

                else:
                    score += 55

                signals.extend(
                    keyword_matches
                )

            supporting_activity = (
                self.CORE_ACTIVITY_MAP.get(
                    usage
                )
            )

            if (
                score
                and supporting_activity
                in activities
            ):
                score += 10

                signals.append(
                    "Firma faaliyeti: "
                    f"{supporting_activity}"
                )

            if score:
                candidates.append({
                    "usage": usage,
                    "usage_name": (
                        self.USAGE_NAMES[
                            usage
                        ]
                    ),
                    "score": min(
                        score,
                        100,
                    ),
                    "matched_signals": list(
                        dict.fromkeys(
                            signals
                        )
                    ),
                    "explicit_purpose": (
                        explicit_purpose
                    ),
                })

        return candidates

    def _match_company_rule(
        self,
        *,
        text: str,
        company: dict,
    ) -> dict | None:
        matches = []

        rules = company.get(
            "classification_rules",
            [],
        )

        if not isinstance(
            rules,
            list,
        ):
            return None

        for rule in rules:
            if not isinstance(
                rule,
                dict,
            ):
                continue

            if (
                rule.get(
                    "active",
                    True,
                )
                is False
            ):
                continue

            usage = self._normalize_usage(
                rule.get(
                    "usage",
                    "",
                )
            )

            if not usage:
                continue

            keywords = rule.get(
                "keywords",
                rule.get(
                    "contains",
                    [],
                ),
            )

            if isinstance(
                keywords,
                str,
            ):
                keywords = [keywords]

            found = self._find_matches(
                text,
                keywords,
            )

            if not found:
                continue

            try:
                confidence = int(
                    rule.get(
                        "confidence",
                        98,
                    )
                )
            except (
                TypeError,
                ValueError,
            ):
                confidence = 98

            matches.append({
                "usage": usage,
                "confidence": confidence,
                "matched_signals": found,
                "account_code": str(
                    rule.get(
                        "account_code",
                        "",
                    )
                ).strip(),
            })

        if not matches:
            return None

        return max(
            matches,
            key=lambda item: item[
                "confidence"
            ],
        )

    def _get_explicit_usage(
        self,
        line_item: dict,
    ) -> str:
        for field_name in [
            "user_selected_usage",
            "accounting_usage",
            "usage_type",
            "usage",
        ]:
            usage = self._normalize_usage(
                line_item.get(
                    field_name,
                    "",
                )
            )

            if usage:
                return usage

        return ""

    def _normalize_usage(
        self,
        value,
    ) -> str:
        normalized = (
            self._normalize_text(
                value
            ).replace(
                " ",
                "_",
            )
        )

        return self.USAGE_ALIASES.get(
            normalized,
            "",
        )

    def _is_mixed_company(
        self,
        company: dict,
    ) -> bool:
        activities = set(
            company.get(
                "activity_types",
                [],
            )
            or []
        )

        primary = str(
            company.get(
                "primary_activity_type",
                company.get(
                    "activity_type",
                    "",
                ),
            )
        ).strip()

        if primary:
            activities.add(primary)

        core_activities = (
            activities.intersection({
                "manufacturing",
                "trading",
                "service",
            })
        )

        return len(
            core_activities
        ) > 1

    def _result(
        self,
        *,
        company: dict,
        status: str,
        usage: str,
        confidence: int,
        source: str,
        matched_signals: list[str],
        candidates: list[dict],
        posting_allowed: bool,
        requires_confirmation: bool,
        reason: str,
        account_code: str = "",
    ) -> dict:
        purpose = self.PURPOSE_MAP.get(
            usage,
            "",
        )

        company_accounts = company.get(
            "default_purchase_accounts",
            {},
        )

        configured_account = (
            account_code
        )

        if (
            not configured_account
            and purpose
            and isinstance(
                company_accounts,
                dict,
            )
        ):
            configured_account = str(
                company_accounts.get(
                    purpose,
                    "",
                )
            ).strip()

        warnings = []

        if status in {
            "ambiguous",
            "unresolved",
        }:
            warnings.append(
                "Kullanım amacı seçilmeden "
                "muhasebe hesabı oluşturulamaz."
            )

        if usage == "fixed_asset":
            warnings.append(
                "Duran varlık hesabı kullanıcı "
                "onayı olmadan kesinleştirilemez."
            )

        if usage and not configured_account:
            warnings.append(
                "Firma profilinde bu kullanım "
                "amacı için hesap tanımlanmamış."
            )

        return {
            "status": status,
            "usage": usage,
            "usage_name": (
                self.USAGE_NAMES.get(
                    usage,
                    "Belirlenemedi",
                )
            ),
            "account_purpose": purpose,
            "configured_account_code": (
                configured_account
            ),
            "confidence": int(
                confidence
            ),
            "source": source,
            "matched_signals": list(
                dict.fromkeys(
                    matched_signals
                )
            ),
            "candidates": candidates,
            "posting_allowed": (
                posting_allowed
            ),
            "requires_user_confirmation": (
                requires_confirmation
            ),
            "reason": reason,
            "warnings": warnings,
        }

    def _unresolved(
        self,
        company: dict,
        reason: str,
    ) -> dict:
        return self._result(
            company=company,
            status="unresolved",
            usage="",
            confidence=0,
            source="unresolved",
            matched_signals=[],
            candidates=[],
            posting_allowed=False,
            requires_confirmation=True,
            reason=reason,
        )

    def _find_matches(
        self,
        text: str,
        keywords: list[str],
    ) -> list[str]:
        return [
            str(keyword)
            for keyword in keywords
            if (
                str(keyword).strip()
                and self._normalize_text(
                    keyword
                ) in text
            )
        ]

    def _normalize_text(
        self,
        value,
    ) -> str:
        value = str(value).translate(
            str.maketrans({
                "ı": "i",
                "İ": "I",
                "ş": "s",
                "Ş": "S",
                "ğ": "g",
                "Ğ": "G",
                "ü": "u",
                "Ü": "U",
                "ö": "o",
                "Ö": "O",
                "ç": "c",
                "Ç": "C",
            })
        )

        normalized = (
            unicodedata.normalize(
                "NFKD",
                value,
            )
        )

        normalized = "".join(
            character
            for character in normalized
            if not unicodedata.combining(
                character
            )
        )

        normalized = re.sub(
            r"[^a-z0-9\s-]",
            " ",
            normalized.casefold(),
        )

        return re.sub(
            r"\s+",
            " ",
            normalized,
        ).strip()
