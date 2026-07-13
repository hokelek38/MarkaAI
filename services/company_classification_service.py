import re
import unicodedata


class CompanyClassificationService:
    """
    Firma profilini imalat, ticaret, hizmet,
    ihracat ve ithalat faaliyetlerine göre sınıflandırır.

    Muhasebe hesabını tek başına belirlemez.
    """

    ACTIVITY_NAMES = {
        "manufacturing": "İmalat / Üretim",
        "trading": "Ticaret / Al-Sat",
        "service": "Hizmet",
        "export": "İhracat",
        "import": "İthalat",
    }

    ACTIVITY_ALIASES = {
        "manufacturing": "manufacturing",
        "imalat": "manufacturing",
        "uretim": "manufacturing",
        "uretici": "manufacturing",

        "trading": "trading",
        "ticaret": "trading",
        "al sat": "trading",
        "al-sat": "trading",
        "toptan": "trading",
        "perakende": "trading",

        "service": "service",
        "hizmet": "service",

        "export": "export",
        "ihracat": "export",

        "import": "import",
        "ithalat": "import",
    }

    ACTIVITY_KEYWORDS = {
        "manufacturing": [
            "imalat",
            "uretim",
            "uretici",
            "fabrika",
            "atolye",
            "sanayi",
            "mamul uretimi",
            "mobilya imalati",
            "tekstil imalati",
        ],
        "trading": [
            "ticaret",
            "alim satim",
            "al sat",
            "toptan satis",
            "perakende satis",
            "magaza",
            "bayilik",
            "e ticaret",
            "ticari mal",
        ],
        "service": [
            "hizmet",
            "danismanlik",
            "yazilim",
            "bakim",
            "onarim",
            "teknik servis",
            "tasimacilik",
            "lojistik",
            "egitim",
            "muhendislik",
        ],
        "export": [
            "ihracat",
            "ihracatci",
            "yurt disi satis",
            "export",
        ],
        "import": [
            "ithalat",
            "ithalatci",
            "yurt disindan alim",
            "import",
        ],
    }

    VALID_ACTIVITIES = set(
        ACTIVITY_NAMES.keys()
    )

    def classify(
        self,
        company_profile: dict,
    ) -> dict:
        """
        Firma profilini sınıflandırır.
        """

        explicit_activities = (
            self._get_explicit_activities(
                company_profile
            )
        )

        primary_activity = (
            self._normalize_activity(
                company_profile.get(
                    "primary_activity_type",
                    company_profile.get(
                        "activity_type",
                        "",
                    ),
                )
            )
        )

        inferred_activities = (
            self._infer_activities(
                company_profile
            )
        )

        flag_activities = (
            self._get_flag_activities(
                company_profile
            )
        )

        activities = []

        for activity in explicit_activities:
            self._append_unique(
                activities,
                activity,
            )

        if primary_activity:
            self._append_unique(
                activities,
                primary_activity,
            )

        for activity in flag_activities:
            self._append_unique(
                activities,
                activity,
            )

        for activity in inferred_activities:
            self._append_unique(
                activities,
                activity,
            )

        if (
            primary_activity
            and primary_activity in activities
        ):
            activities.remove(
                primary_activity
            )
            activities.insert(
                0,
                primary_activity,
            )

        source, confidence = (
            self._determine_source_and_confidence(
                explicit_activities=(
                    explicit_activities
                ),
                primary_activity=primary_activity,
                flag_activities=flag_activities,
                inferred_activities=(
                    inferred_activities
                ),
            )
        )

        warnings = []

        if not activities:
            warnings.append(
                "Firma faaliyet türü belirlenemedi."
            )

        if source == "description_inference":
            warnings.append(
                "Faaliyet türü açıklama alanlarından "
                "tahmin edildi. Kullanıcı onayı gerekir."
            )

        if len(activities) > 1:
            warnings.append(
                "Firma karma faaliyetlidir. Her fatura "
                "kaleminin kullanım amacı ayrıca "
                "belirlenmelidir."
            )

        if (
            primary_activity
            and primary_activity
            not in explicit_activities
            and explicit_activities
        ):
            warnings.append(
                "Ana faaliyet, faaliyet türleri listesinde "
                "açıkça bulunmuyor."
            )

        requires_confirmation = (
            not activities
            or confidence < 90
        )

        return {
            "company_id": company_profile.get(
                "company_id",
                "",
            ),
            "company_title": company_profile.get(
                "title",
                "",
            ),
            "primary_activity": (
                primary_activity
                or (
                    activities[0]
                    if activities
                    else ""
                )
            ),
            "primary_activity_name": (
                self.ACTIVITY_NAMES.get(
                    primary_activity
                    or (
                        activities[0]
                        if activities
                        else ""
                    ),
                    "Tanımlanmadı",
                )
            ),
            "activity_types": activities,
            "activity_names": [
                self.ACTIVITY_NAMES.get(
                    activity,
                    activity,
                )
                for activity in activities
            ],
            "is_manufacturing": (
                "manufacturing" in activities
            ),
            "is_trading": (
                "trading" in activities
            ),
            "is_service": (
                "service" in activities
            ),
            "is_exporter": (
                "export" in activities
            ),
            "is_importer": (
                "import" in activities
            ),
            "is_multi_activity": (
                len(activities) > 1
            ),
            "inventory_enabled": bool(
                company_profile.get(
                    "inventory_enabled",
                    False,
                )
            ),
            "production_enabled": bool(
                company_profile.get(
                    "production_enabled",
                    False,
                )
            ),
            "service_production_enabled": bool(
                company_profile.get(
                    "service_production_enabled",
                    False,
                )
            ),
            "classification_source": source,
            "confidence": confidence,
            "requires_user_confirmation": (
                requires_confirmation
            ),
            "posting_allowed": bool(
                activities
            ),
            "warnings": warnings,
            "posting_principle": (
                "Hesap seçimi yalnızca firma türüne göre "
                "yapılamaz. Belge türü, fatura kalemi, "
                "kullanım amacı ve firma politikası "
                "birlikte değerlendirilmelidir."
            ),
        }

    def _get_explicit_activities(
        self,
        company_profile: dict,
    ) -> list[str]:
        values = company_profile.get(
            "activity_types",
            [],
        )

        if isinstance(values, str):
            values = [values]

        if not isinstance(values, list):
            return []

        activities = []

        for value in values:
            activity = self._normalize_activity(
                value
            )

            self._append_unique(
                activities,
                activity,
            )

        return activities

    def _get_flag_activities(
        self,
        company_profile: dict,
    ) -> list[str]:
        activities = []

        if company_profile.get(
            "production_enabled"
        ):
            activities.append(
                "manufacturing"
            )

        if company_profile.get(
            "service_production_enabled"
        ):
            activities.append(
                "service"
            )

        return activities

    def _infer_activities(
        self,
        company_profile: dict,
    ) -> list[str]:
        search_text = self._build_search_text(
            company_profile
        )

        activities = []

        for activity, keywords in (
            self.ACTIVITY_KEYWORDS.items()
        ):
            for keyword in keywords:
                if (
                    self._normalize_text(keyword)
                    in search_text
                ):
                    self._append_unique(
                        activities,
                        activity,
                    )
                    break

        return activities

    def _build_search_text(
        self,
        company_profile: dict,
    ) -> str:
        values = [
            company_profile.get(
                "sector",
                "",
            ),
            company_profile.get(
                "activity_description",
                "",
            ),
            company_profile.get(
                "business_description",
                "",
            ),
            company_profile.get(
                "nace_description",
                "",
            ),
        ]

        nace_codes = company_profile.get(
            "nace_codes",
            [],
        )

        if isinstance(nace_codes, list):
            values.extend(nace_codes)

        return self._normalize_text(
            " ".join(
                str(value)
                for value in values
                if value
            )
        )

    def _normalize_activity(
        self,
        value,
    ) -> str:
        normalized = self._normalize_text(
            value
        )

        activity = self.ACTIVITY_ALIASES.get(
            normalized,
            normalized,
        )

        if activity in self.VALID_ACTIVITIES:
            return activity

        return ""

    def _determine_source_and_confidence(
        self,
        *,
        explicit_activities: list[str],
        primary_activity: str,
        flag_activities: list[str],
        inferred_activities: list[str],
    ) -> tuple[str, int]:
        if explicit_activities:
            return "company_profile", 99

        if primary_activity:
            return "primary_activity", 95

        if flag_activities:
            return "operational_flags", 85

        if inferred_activities:
            return "description_inference", 65

        return "unresolved", 0

    def _append_unique(
        self,
        target: list[str],
        value: str,
    ) -> None:
        if (
            value
            and value not in target
        ):
            target.append(value)

    def _normalize_text(
        self,
        value,
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

        normalized = normalized.casefold()

        normalized = re.sub(
            r"[^a-z0-9\s-]",
            " ",
            normalized,
        )

        return re.sub(
            r"\s+",
            " ",
            normalized,
        ).strip()
