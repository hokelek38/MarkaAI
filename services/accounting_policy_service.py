from copy import deepcopy


class AccountingPolicyService:
    """
    Firma bazlı muhasebe politikalarını yönetir.

    Bu servis hesap seçimini tek başına kesinleştirmez.
    Firma faaliyetini, kullanım amacını ve kullanıcı tarafından
    tanımlanan hesap tercihlerini bir araya getirir.
    """

    DEFAULT_POLICY = {
        "cost_system": "7A",
        "service_cost_method": "740",
        "telecom_usage": "administrative",
        "accounts": {
            "raw_material": "150",
            "trade_goods": "153",
            "machinery": "253",
            "vehicles": "254",
            "fixtures": "255",
            "production_overhead": "730",
            "service_cost": "740",
            "selling_expense": "760",
            "administrative_expense": "770",
            "finance_expense": "780",
            "deductible_vat": "191",
            "suppliers": "320",

            # Firma tarafından özellikle tanımlanmalıdır.
            "oiv_account": "",
            "factoring_counter_account": "",
        },
    }

    USAGE_ACCOUNT_KEYS = {
        "production": "raw_material",
        "resale": "trade_goods",
        "machinery": "machinery",
        "vehicle": "vehicles",
        "fixed_asset": "fixtures",
        "production_overhead": (
            "production_overhead"
        ),
        "service_production": "service_cost",
        "selling": "selling_expense",
        "administrative": (
            "administrative_expense"
        ),
        "finance": "finance_expense",
    }

    TELECOM_USAGE_KEYS = {
        "production": "production_overhead",
        "service_production": "service_cost",
        "selling": "selling_expense",
        "administrative": (
            "administrative_expense"
        ),
    }

    ACTIVITY_TYPES = {
        "manufacturing",
        "trading",
        "service",
        "export",
        "import",
    }

    def build_policy(
        self,
        company: dict,
    ) -> dict:
        """
        Varsayılan politika ile firma tercihlerini birleştirir.
        """

        policy = deepcopy(
            self.DEFAULT_POLICY
        )

        company_policy = company.get(
            "accounting_policy",
            {},
        )

        if isinstance(company_policy, dict):
            for key in [
                "cost_system",
                "service_cost_method",
                "telecom_usage",
            ]:
                value = company_policy.get(key)

                if value not in {
                    None,
                    "",
                }:
                    policy[key] = value

            policy_accounts = company_policy.get(
                "accounts",
                {},
            )

            if isinstance(
                policy_accounts,
                dict,
            ):
                policy["accounts"].update(
                    {
                        str(key): str(value)
                        for key, value
                        in policy_accounts.items()
                        if value not in {
                            None,
                            "",
                        }
                    }
                )

        # Eski profil yapısıyla geriye uyumluluk
        default_purchase_accounts = (
            company.get(
                "default_purchase_accounts",
                {},
            )
        )

        if isinstance(
            default_purchase_accounts,
            dict,
        ):
            compatibility_map = {
                "raw_material": "raw_material",
                "trade_goods": "trade_goods",
                "fixed_asset": "fixtures",
                "direct_service_cost": (
                    "service_cost"
                ),
                "service_cost": "service_cost",
                "selling_expense": (
                    "selling_expense"
                ),
                "administrative_expense": (
                    "administrative_expense"
                ),
                "finance_expense": (
                    "finance_expense"
                ),
            }

            for old_key, new_key in (
                compatibility_map.items()
            ):
                value = (
                    default_purchase_accounts.get(
                        old_key
                    )
                )

                if value not in {
                    None,
                    "",
                }:
                    policy["accounts"][
                        new_key
                    ] = str(value)

        policy["activity_types"] = (
            self.get_activity_types(
                company
            )
        )

        return policy

    def get_activity_types(
        self,
        company: dict,
    ) -> list[str]:
        """
        Firmanın bütün faaliyet türlerini döndürür.
        """

        activities = []

        raw_activities = company.get(
            "activity_types",
            [],
        )

        if isinstance(
            raw_activities,
            str,
        ):
            raw_activities = [
                raw_activities
            ]

        for activity in raw_activities:
            normalized = str(
                activity
            ).strip()

            if (
                normalized
                and normalized
                in self.ACTIVITY_TYPES
                and normalized
                not in activities
            ):
                activities.append(
                    normalized
                )

        primary_activity = str(
            company.get(
                "primary_activity_type",
                company.get(
                    "activity_type",
                    "",
                ),
            )
        ).strip()

        if (
            primary_activity
            and primary_activity
            in self.ACTIVITY_TYPES
            and primary_activity
            not in activities
        ):
            activities.insert(
                0,
                primary_activity,
            )

        return activities

    def resolve_purchase_account(
        self,
        *,
        company: dict,
        usage: str,
    ) -> dict:
        """
        Kullanım amacına göre firma hesap politikasını döndürür.
        """

        policy = self.build_policy(
            company
        )

        account_key = (
            self.USAGE_ACCOUNT_KEYS.get(
                usage
            )
        )

        if not account_key:
            return {
                "account_code": "",
                "account_key": "",
                "usage": usage,
                "confidence": 0,
                "requires_confirmation": True,
                "reason": (
                    "Kullanım amacı için hesap "
                    "politikası tanımlı değildir."
                ),
            }

        account_code = str(
            policy["accounts"].get(
                account_key,
                "",
            )
        ).strip()

        return {
            "account_code": account_code,
            "account_key": account_key,
            "usage": usage,
            "confidence": (
                90
                if account_code
                else 0
            ),
            "requires_confirmation": (
                not bool(account_code)
            ),
            "reason": (
                "Hesap firma muhasebe "
                "politikasından alındı."
                if account_code
                else
                "Firma muhasebe politikasında "
                "hesap tanımlanmamıştır."
            ),
        }

    def get_telecom_policy(
        self,
        company: dict,
    ) -> dict:
        """
        Telefon ve internet faturası için firma politikasını döndürür.
        """

        policy = self.build_policy(
            company
        )

        telecom_usage = str(
            policy.get(
                "telecom_usage",
                "administrative",
            )
        ).strip()

        account_key = (
            self.TELECOM_USAGE_KEYS.get(
                telecom_usage,
                "administrative_expense",
            )
        )

        base_account = str(
            policy["accounts"].get(
                account_key,
                "",
            )
        ).strip()

        oiv_account = str(
            policy["accounts"].get(
                "oiv_account",
                "",
            )
        ).strip()

        return {
            "usage": telecom_usage,
            "base_account": base_account,
            "vat_account": str(
                policy["accounts"].get(
                    "deductible_vat",
                    "191",
                )
            ),
            "supplier_account": str(
                policy["accounts"].get(
                    "suppliers",
                    "320",
                )
            ),
            "oiv_account": oiv_account,
            "requires_confirmation": (
                not bool(base_account)
                or not bool(oiv_account)
            ),
            "warnings": self._build_missing_warnings(
                {
                    "Telefon gider hesabı": (
                        base_account
                    ),
                    "ÖİV hesabı": oiv_account,
                }
            ),
        }

    def get_factoring_policy(
        self,
        company: dict,
    ) -> dict:
        """
        Faktoring faturası için firma politikasını döndürür.
        """

        policy = self.build_policy(
            company
        )

        finance_account = str(
            policy["accounts"].get(
                "finance_expense",
                "",
            )
        ).strip()

        counter_account = str(
            policy["accounts"].get(
                "factoring_counter_account",
                "",
            )
        ).strip()

        return {
            "interest_account": (
                finance_account
            ),
            "commission_account": (
                finance_account
            ),
            "bsmv_account": finance_account,
            "counter_account": (
                counter_account
            ),
            "vat_account": None,
            "requires_confirmation": (
                not bool(finance_account)
                or not bool(counter_account)
            ),
            "warnings": self._build_missing_warnings(
                {
                    "Finansman gider hesabı": (
                        finance_account
                    ),
                    "Faktoring karşı hesabı": (
                        counter_account
                    ),
                }
            ),
        }

    def validate_policy(
        self,
        company: dict,
    ) -> dict:
        """
        Firma muhasebe politikasındaki eksikleri kontrol eder.
        """

        policy = self.build_policy(
            company
        )

        errors = []
        warnings = []

        activities = policy.get(
            "activity_types",
            [],
        )

        if not activities:
            errors.append(
                "Firma faaliyet türü tanımlanmamış."
            )

        required_accounts = {
            "deductible_vat": (
                "İndirilecek KDV hesabı"
            ),
            "suppliers": "Satıcı hesabı",
            "administrative_expense": (
                "Genel yönetim gider hesabı"
            ),
        }

        if "manufacturing" in activities:
            required_accounts.update({
                "raw_material": (
                    "İlk madde ve malzeme hesabı"
                ),
                "production_overhead": (
                    "Üretim genel gider hesabı"
                ),
            })

        if "trading" in activities:
            required_accounts[
                "trade_goods"
            ] = "Ticari mallar hesabı"

        if "service" in activities:
            required_accounts[
                "service_cost"
            ] = "Hizmet maliyet hesabı"

        for account_key, title in (
            required_accounts.items()
        ):
            account_code = str(
                policy["accounts"].get(
                    account_key,
                    "",
                )
            ).strip()

            if not account_code:
                errors.append(
                    f"{title} tanımlanmamış."
                )

        if not policy["accounts"].get(
            "oiv_account"
        ):
            warnings.append(
                (
                    "Telefon faturaları için "
                    "ÖİV hesabı tanımlanmamış."
                )
            )

        if not policy["accounts"].get(
            "factoring_counter_account"
        ):
            warnings.append(
                (
                    "Faktoring işlemleri için "
                    "karşı hesap tanımlanmamış."
                )
            )

        return {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "policy": policy,
        }

    def _build_missing_warnings(
        self,
        fields: dict,
    ) -> list[str]:
        warnings = []

        for title, value in fields.items():
            if not str(value).strip():
                warnings.append(
                    f"{title} tanımlanmamış."
                )

        return warnings
