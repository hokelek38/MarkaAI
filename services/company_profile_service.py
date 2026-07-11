import json
from pathlib import Path


class CompanyProfileService:
    """
    Firma profillerini okur ve firmanın faaliyet yapısını diğer servislere sunar.

    Bu servis:
    - Firma profilini okur.
    - Firma faaliyet türünü bildirir.
    - Firmaya özel hesap tercihlerini getirir.
    - Muhasebe hesabını tek başına seçmez.
    """

    def __init__(self):
        project_root = Path(__file__).resolve().parent.parent

        self.profile_file = (
            project_root
            / "data"
            / "company_profiles.json"
        )

        self.profile_data = self._load_profiles()
        self.companies = self.profile_data.get("companies", [])

    def _load_profiles(self) -> dict:
        """
        Firma profilleri JSON dosyasını okuyup sözlük olarak döndürür.
        """

        if not self.profile_file.exists():
            raise FileNotFoundError(
                "Firma profilleri dosyası bulunamadı:\n"
                f"{self.profile_file}"
            )

        try:
            with self.profile_file.open(
                "r",
                encoding="utf-8",
            ) as file:
                return json.load(file)

        except json.JSONDecodeError as error:
            raise ValueError(
                "Firma profilleri dosyası geçerli JSON biçiminde değil.\n"
                f"Satır: {error.lineno}, sütun: {error.colno}\n"
                f"Detay: {error.msg}"
            ) from error

    def get_metadata(self) -> dict:
        """
        Firma profilleri veri tabanının sürüm bilgisini döndürür.
        """

        return self.profile_data.get("metadata", {}).copy()

    def get_all_companies(
        self,
        active_only: bool = True,
    ) -> list[dict]:
        """
        Bütün firma profillerini döndürür.

        active_only=True ise yalnızca aktif firmalar döner.
        """

        if not active_only:
            return [
                company.copy()
                for company in self.companies
            ]

        return [
            company.copy()
            for company in self.companies
            if company.get("active") is True
        ]

    def get_company_by_id(
        self,
        company_id: str,
    ) -> dict | None:
        """
        Firma kimliğine göre firma profilini döndürür.
        """

        normalized_id = str(company_id).strip()

        for company in self.companies:
            if company.get("company_id") == normalized_id:
                return company.copy()

        return None

    def get_company_by_tax_number(
        self,
        tax_number: str,
    ) -> dict | None:
        """
        VKN veya TCKN bilgisine göre firma profilini döndürür.
        """

        normalized_tax_number = str(tax_number).strip()

        for company in self.companies:
            company_tax_number = str(
                company.get("tax_number", "")
            ).strip()

            if company_tax_number == normalized_tax_number:
                return company.copy()

        return None

    def get_company_title(
        self,
        company_id: str,
    ) -> str:
        """
        Firma kimliğine göre firma unvanını döndürür.
        """

        company = self.get_company_by_id(company_id)

        if not company:
            return "Firma bulunamadı"

        return company.get(
            "title",
            "Firma unvanı bulunamadı",
        )

    def get_activity_type(
        self,
        company_id: str,
    ) -> str:
        """
        Firmanın faaliyet türünü döndürür.

        Desteklenen değerler:
        manufacturing
        trading
        service
        """

        company = self.get_company_by_id(company_id)

        if not company:
            return ""

        return company.get("activity_type", "")

    def get_default_account(
        self,
        company_id: str,
        purpose: str,
    ) -> str | None:
        """
        Firmanın belirli kullanım amacı için varsayılan hesabını döndürür.

        Örnek amaçlar:
        raw_material
        trade_goods
        fixed_asset
        administrative_expense
        selling_expense
        service_cost
        direct_service_cost
        """

        company = self.get_company_by_id(company_id)

        if not company:
            return None

        default_accounts = company.get(
            "default_purchase_accounts",
            {},
        )

        return default_accounts.get(purpose)

    def get_classification_rules(
        self,
        company_id: str,
    ) -> list[dict]:
        """
        Firmaya özel sınıflandırma kurallarını döndürür.
        """

        company = self.get_company_by_id(company_id)

        if not company:
            return []

        return [
            rule.copy()
            for rule in company.get(
                "classification_rules",
                [],
            )
        ]

    def find_matching_rules(
        self,
        company_id: str,
        invoice_text: str,
    ) -> list[dict]:
        """
        Fatura metnine uyan firma kurallarını döndürür.
        """

        normalized_text = str(invoice_text).casefold()
        matching_rules = []

        for rule in self.get_classification_rules(company_id):
            keywords = rule.get("keywords", [])

            if not keywords:
                continue

            matched_keywords = [
                keyword
                for keyword in keywords
                if str(keyword).casefold() in normalized_text
            ]

            if matched_keywords:
                result = rule.copy()
                result["matched_keywords"] = matched_keywords
                matching_rules.append(result)

        return matching_rules

    def get_learning_settings(
        self,
        company_id: str,
    ) -> dict:
        """
        Firmanın kontrollü öğrenme ayarlarını döndürür.
        """

        company = self.get_company_by_id(company_id)

        if not company:
            return {}

        return company.get(
            "learning_settings",
            {},
        ).copy()

    def is_learning_enabled(
        self,
        company_id: str,
    ) -> bool:
        """
        Firma için kontrollü öğrenmenin açık olup olmadığını döndürür.
        """

        settings = self.get_learning_settings(company_id)

        return bool(
            settings.get("enabled", False)
        )

    def requires_professional_approval(
        self,
        company_id: str,
    ) -> bool:
        """
        Öğrenilen öneriler için mali müşavir onayının zorunlu olup olmadığını döndürür.
        """

        settings = self.get_learning_settings(company_id)

        return bool(
            settings.get(
                "requires_professional_approval",
                True,
            )
        )

    def validate_company_profile(
        self,
        company_id: str,
    ) -> dict:
        """
        Firma profilindeki temel alanların dolu ve geçerli olup olmadığını kontrol eder.
        """

        company = self.get_company_by_id(company_id)

        if not company:
            return {
                "is_valid": False,
                "errors": [
                    "Firma profili bulunamadı."
                ],
                "warnings": [],
            }

        errors = []
        warnings = []

        required_fields = [
            "company_id",
            "title",
            "tax_number",
            "activity_type",
            "sector",
        ]

        for field in required_fields:
            value = company.get(field)

            if value is None:
                errors.append(
                    f"Firma profilinde zorunlu alan eksik: {field}"
                )
                continue

            if isinstance(value, str) and not value.strip():
                errors.append(
                    f"Firma profilinde zorunlu alan boş: {field}"
                )
                continue

            if isinstance(value, (list, dict)) and len(value) == 0:
                errors.append(
                    f"Firma profilinde zorunlu alan boş: {field}"
                )

        tax_number = str(
            company.get("tax_number", "")
        ).strip()

        if not tax_number.isdigit():
            errors.append(
                "Firma VKN/TCKN bilgisi yalnızca rakamlardan oluşmalıdır."
            )

        elif len(tax_number) not in {10, 11}:
            errors.append(
                "Firma VKN/TCKN bilgisi 10 veya 11 haneli olmalıdır."
            )

        supported_activity_types = {
            "manufacturing",
            "trading",
            "service",
        }

        activity_type = company.get("activity_type")

        if activity_type not in supported_activity_types:
            errors.append(
                "Firma faaliyet türü desteklenen değerlerden biri değil."
            )

        if not company.get("nace_codes"):
            warnings.append(
                "Firma profilinde NACE kodu bulunmuyor."
            )

        default_accounts = company.get(
            "default_purchase_accounts",
            {},
        )

        if not default_accounts:
            warnings.append(
                "Firma profilinde varsayılan alış hesapları tanımlanmamış."
            )

        if company.get("activity_type") == "manufacturing":
            if not company.get("production_enabled"):
                warnings.append(
                    "Firma imalat işletmesi olarak tanımlı ancak üretim özelliği kapalı."
                )

        if company.get("activity_type") == "trading":
            if not company.get("inventory_enabled"):
                warnings.append(
                    "Firma alım-satım işletmesi olarak tanımlı ancak stok takibi kapalı."
                )

        if company.get("activity_type") == "service":
            if not company.get("service_production_enabled"):
                warnings.append(
                    "Firma hizmet işletmesi olarak tanımlı ancak hizmet üretimi özelliği kapalı."
                )

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }