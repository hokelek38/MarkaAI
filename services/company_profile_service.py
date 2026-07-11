import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from uuid import uuid4


class CompanyProfileService:
    """
    MarkaAI firma profillerini yönetir.

    Görevleri:
    - Firma eklemek
    - Firma bilgilerini güncellemek
    - Firmaları kalıcı olarak JSON dosyasına kaydetmek
    - VKN/TCKN üzerinden firma bulmak
    - Firmanın faaliyet ve hesap tercihlerini döndürmek
    """

    ALLOWED_ACTIVITY_TYPES = {
        "manufacturing": "Üretim",
        "trading": "Ticaret / Al-Sat",
        "service": "Hizmet",
        "export": "İhracat",
        "import": "İthalat",
    }

    def __init__(
        self,
        data_file: str | Path | None = None,
    ):
        if data_file is None:
            project_root = Path(__file__).resolve().parents[1]
            data_file = (
                project_root
                / "data"
                / "company_profiles.json"
            )

        self.data_file = Path(data_file)
        self._ensure_storage()

    def get_all_companies(
        self,
        active_only: bool = True,
    ) -> list[dict]:
        """
        Kayıtlı firmaları döndürür.
        """

        data = self._load_data()
        companies = data.get("companies", [])

        if active_only:
            companies = [
                company
                for company in companies
                if company.get("active", True)
            ]

        return deepcopy(companies)

    def find_company(
        self,
        company_id: str,
    ) -> dict | None:
        """
        Firma kimliğine göre firma bulur.
        """

        normalized_id = str(company_id).strip()

        for company in self.get_all_companies(
            active_only=False
        ):
            if company.get("company_id") == normalized_id:
                return company

        return None

    def get_company_by_id(
        self,
        company_id: str,
    ) -> dict | None:
        """
        find_company metodunun geriye uyumlu karşılığıdır.
        """

        return self.find_company(company_id)

    def get_company_profile(
        self,
        company_id: str,
    ) -> dict | None:
        return self.find_company(company_id)

    def find_company_by_tax_number(
        self,
        tax_number: str,
    ) -> dict | None:
        """
        VKN veya TCKN üzerinden firma bulur.
        """

        normalized_tax_number = (
            self._normalize_tax_number(tax_number)
        )

        if not normalized_tax_number:
            return None

        for company in self.get_all_companies(
            active_only=False
        ):
            company_tax_number = (
                self._normalize_tax_number(
                    company.get("tax_number", "")
                )
            )

            if (
                company_tax_number
                == normalized_tax_number
            ):
                return company

        return None

    def add_company(
        self,
        company_data: dict | None = None,
        **kwargs,
    ) -> dict:
        """
        Yeni firma oluşturur ve JSON dosyasına kaydeder.

        company_data sözlük olarak veya alanlar ayrı ayrı
        gönderilebilir.
        """

        payload = {}

        if company_data:
            if not isinstance(company_data, dict):
                raise TypeError(
                    "Firma bilgileri sözlük biçiminde olmalıdır."
                )

            payload.update(company_data)

        payload.update(kwargs)

        title = str(
            payload.get("title", "")
        ).strip()

        tax_number = self._normalize_tax_number(
            payload.get("tax_number", "")
        )

        activity_types = self._normalize_activity_types(
            payload.get(
                "activity_types",
                payload.get("activity_type"),
            )
        )

        primary_activity_type = str(
            payload.get(
                "primary_activity_type",
                activity_types[0]
                if activity_types
                else "",
            )
        ).strip().casefold()

        self._validate_required_fields(
            title=title,
            tax_number=tax_number,
            activity_types=activity_types,
            primary_activity_type=primary_activity_type,
        )

        existing_company = (
            self.find_company_by_tax_number(
                tax_number
            )
        )

        if existing_company:
            raise ValueError(
                "Bu VKN/TCKN ile kayıtlı bir firma zaten var:\n"
                f"{existing_company.get('title', '-')}"
            )

        now = datetime.now().isoformat(
            timespec="seconds"
        )

        default_accounts = (
            self._build_default_purchase_accounts(
                activity_types
            )
        )

        supplied_accounts = payload.get(
            "default_purchase_accounts",
            {},
        )

        if isinstance(supplied_accounts, dict):
            default_accounts.update(
                supplied_accounts
            )

        company = {
            "company_id": self._generate_company_id(
                tax_number
            ),
            "title": title,
            "tax_number": tax_number,
            "activity_types": activity_types,
            "primary_activity_type": (
                primary_activity_type
            ),

            # Eski servislerle uyumluluk için korunuyor.
            "activity_type": primary_activity_type,

            "sector": str(
                payload.get("sector", "")
            ).strip(),
            "activity_description": str(
                payload.get(
                    "activity_description",
                    "",
                )
            ).strip(),
            "nace_codes": self._normalize_list(
                payload.get("nace_codes", [])
            ),
            "inventory_enabled": bool(
                payload.get(
                    "inventory_enabled",
                    self._has_inventory_activity(
                        activity_types
                    ),
                )
            ),
            "production_enabled": bool(
                payload.get(
                    "production_enabled",
                    "manufacturing"
                    in activity_types,
                )
            ),
            "service_production_enabled": bool(
                payload.get(
                    "service_production_enabled",
                    "service" in activity_types,
                )
            ),
            "default_purchase_accounts": (
                default_accounts
            ),
            "classification_rules": list(
                payload.get(
                    "classification_rules",
                    [],
                )
            ),
            "learning_settings": self._build_learning_settings(
                payload.get(
                    "learning_settings",
                    {},
                )
            ),
            "erp_system": str(
                payload.get("erp_system", "")
            ).strip(),
            "erp_company_code": str(
                payload.get(
                    "erp_company_code",
                    "",
                )
            ).strip(),
            "active": bool(
                payload.get("active", True)
            ),
            "license_active": bool(
                payload.get(
                    "license_active",
                    True,
                )
            ),
            "created_at": now,
            "updated_at": now,
        }

        data = self._load_data()
        data.setdefault("companies", [])
        data["companies"].append(company)

        self._save_data(data)

        return deepcopy(company)

    def create_company(
        self,
        company_data: dict | None = None,
        **kwargs,
    ) -> dict:
        """
        add_company metodunun alternatif adıdır.
        """

        return self.add_company(
            company_data,
            **kwargs,
        )

    def update_company(
        self,
        company_id: str,
        updates: dict | None = None,
        **kwargs,
    ) -> dict:
        """
        Kayıtlı firmanın bilgilerini günceller.
        """

        update_data = {}

        if updates:
            if not isinstance(updates, dict):
                raise TypeError(
                    "Güncellenecek bilgiler sözlük olmalıdır."
                )

            update_data.update(updates)

        update_data.update(kwargs)

        data = self._load_data()
        companies = data.get("companies", [])

        company_index = None

        for index, company in enumerate(companies):
            if company.get("company_id") == company_id:
                company_index = index
                break

        if company_index is None:
            raise ValueError(
                f"Firma bulunamadı: {company_id}"
            )

        current_company = companies[company_index]
        updated_company = deepcopy(current_company)
        updated_company.update(update_data)

        title = str(
            updated_company.get("title", "")
        ).strip()

        tax_number = self._normalize_tax_number(
            updated_company.get(
                "tax_number",
                "",
            )
        )

        activity_types = self._normalize_activity_types(
            updated_company.get(
                "activity_types",
                updated_company.get(
                    "activity_type",
                ),
            )
        )

        primary_activity_type = str(
            updated_company.get(
                "primary_activity_type",
                activity_types[0]
                if activity_types
                else "",
            )
        ).strip().casefold()

        self._validate_required_fields(
            title=title,
            tax_number=tax_number,
            activity_types=activity_types,
            primary_activity_type=primary_activity_type,
        )

        duplicate_company = (
            self.find_company_by_tax_number(
                tax_number
            )
        )

        if (
            duplicate_company
            and duplicate_company.get(
                "company_id"
            )
            != company_id
        ):
            raise ValueError(
                "Bu VKN/TCKN başka bir firmada kayıtlı."
            )

        default_accounts = (
            self._build_default_purchase_accounts(
                activity_types
            )
        )

        current_accounts = updated_company.get(
            "default_purchase_accounts",
            {},
        )

        if isinstance(current_accounts, dict):
            default_accounts.update(
                current_accounts
            )

        updated_company.update({
            "company_id": company_id,
            "title": title,
            "tax_number": tax_number,
            "activity_types": activity_types,
            "primary_activity_type": (
                primary_activity_type
            ),
            "activity_type": primary_activity_type,
            "default_purchase_accounts": (
                default_accounts
            ),
            "inventory_enabled": bool(
                updated_company.get(
                    "inventory_enabled",
                    self._has_inventory_activity(
                        activity_types
                    ),
                )
            ),
            "production_enabled": bool(
                updated_company.get(
                    "production_enabled",
                    "manufacturing"
                    in activity_types,
                )
            ),
            "service_production_enabled": bool(
                updated_company.get(
                    "service_production_enabled",
                    "service" in activity_types,
                )
            ),
            "nace_codes": self._normalize_list(
                updated_company.get(
                    "nace_codes",
                    [],
                )
            ),
            "learning_settings": (
                self._build_learning_settings(
                    updated_company.get(
                        "learning_settings",
                        {},
                    )
                )
            ),
            "updated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
        })

        companies[company_index] = updated_company
        data["companies"] = companies

        self._save_data(data)

        return deepcopy(updated_company)

    def deactivate_company(
        self,
        company_id: str,
    ) -> dict:
        """
        Firmayı silmeden pasif hale getirir.
        """

        return self.update_company(
            company_id,
            active=False,
        )

    def activate_company(
        self,
        company_id: str,
    ) -> dict:
        """
        Pasif firmayı yeniden aktifleştirir.
        """

        return self.update_company(
            company_id,
            active=True,
        )

    def get_activity_types(
        self,
        company_id: str,
    ) -> list[str]:
        company = self.find_company(company_id)

        if not company:
            return []

        return self._normalize_activity_types(
            company.get(
                "activity_types",
                company.get("activity_type"),
            )
        )

    def get_activity_type(
        self,
        company_id: str,
    ) -> str:
        """
        Firmanın öncelikli faaliyet türünü döndürür.
        """

        company = self.find_company(company_id)

        if not company:
            return ""

        return str(
            company.get(
                "primary_activity_type",
                company.get(
                    "activity_type",
                    "",
                ),
            )
        ).strip()

    def get_company_activity_type(
        self,
        company_id: str,
    ) -> str:
        return self.get_activity_type(company_id)

    def get_default_purchase_accounts(
        self,
        company_id: str,
    ) -> dict:
        company = self.find_company(company_id)

        if not company:
            return {}

        accounts = company.get(
            "default_purchase_accounts",
            {},
        )

        if not isinstance(accounts, dict):
            return {}

        return deepcopy(accounts)

    def get_default_purchase_account(
        self,
        company_id: str,
        usage_purpose: str,
    ) -> str | None:
        accounts = (
            self.get_default_purchase_accounts(
                company_id
            )
        )

        return accounts.get(usage_purpose)

    def get_classification_rules(
        self,
        company_id: str,
    ) -> list[dict]:
        company = self.find_company(company_id)

        if not company:
            return []

        rules = company.get(
            "classification_rules",
            [],
        )

        if not isinstance(rules, list):
            return []

        return deepcopy(rules)

    def get_company_rules(
        self,
        company_id: str,
    ) -> list[dict]:
        return self.get_classification_rules(
            company_id
        )

    def find_matching_rules(
        self,
        company_id: str,
        text=None,
        invoice_data: dict | None = None,
        **kwargs,
    ) -> list[dict]:
        """
        Fatura metniyle eşleşen firmaya özel sınıflandırma
        kurallarını döndürür.

        Eski ve yeni AccountingService çağrılarıyla uyumludur.
        """

        if not self.find_company(company_id):
            return []

        rules = self.get_classification_rules(
            company_id
        )

        if isinstance(text, dict):
            invoice_data = text
            text = None

        if invoice_data is None:
            for key in (
                "document_data",
                "data",
                "invoice",
            ):
                candidate = kwargs.get(key)

                if isinstance(candidate, dict):
                    invoice_data = candidate
                    break

        text_parts = []

        if text is not None:
            text_parts.append(str(text))

        if isinstance(invoice_data, dict):
            for key in (
                "raw_text",
                "description",
                "item_description",
                "product_name",
            ):
                value = invoice_data.get(key)

                if value:
                    text_parts.append(str(value))

        for key in (
            "raw_text",
            "product_text",
            "description",
            "content_text",
        ):
            value = kwargs.get(key)

            if value:
                text_parts.append(str(value))

        normalized_text = " ".join(
            text_parts
        ).casefold()

        matched_rules = []
        fallback_rules = []

        for rule in rules:
            if not isinstance(rule, dict):
                continue

            keywords = [
                str(keyword).strip().casefold()
                for keyword in rule.get(
                    "keywords",
                    [],
                )
                if str(keyword).strip()
            ]

            rule_result = dict(rule)

            # Anahtar kelimesiz kural varsayılan kuraldır.
            if not keywords:
                rule_result["matched_keywords"] = []
                fallback_rules.append(rule_result)
                continue

            matched_keywords = [
                keyword
                for keyword in keywords
                if keyword in normalized_text
            ]

            if matched_keywords:
                rule_result["matched_keywords"] = (
                    matched_keywords
                )
                matched_rules.append(rule_result)

        matched_rules.sort(
            key=lambda rule: int(
                rule.get("confidence", 0) or 0
            ),
            reverse=True,
        )

        fallback_rules.sort(
            key=lambda rule: int(
                rule.get("confidence", 0) or 0
            ),
            reverse=True,
        )

        if matched_rules:
            return matched_rules

        return fallback_rules

    def get_learning_settings(
        self,
        company_id: str,
    ) -> dict:
        company = self.find_company(company_id)

        if not company:
            return {}

        settings = company.get(
            "learning_settings",
            {},
        )

        if not isinstance(settings, dict):
            return {}

        return deepcopy(settings)

    def validate_profile(
        self,
        company_or_id,
    ) -> dict:
        """
        Firma profilinin temel alanlarını kontrol eder.
        """

        if isinstance(company_or_id, dict):
            company = company_or_id
        else:
            company = self.find_company(
                str(company_or_id)
            )

        errors = []
        warnings = []

        if not company:
            errors.append(
                "Firma profili bulunamadı."
            )

            return {
                "is_valid": False,
                "errors": errors,
                "warnings": warnings,
            }

        title = str(
            company.get("title", "")
        ).strip()

        tax_number = self._normalize_tax_number(
            company.get("tax_number", "")
        )

        activity_types = self._normalize_activity_types(
            company.get(
                "activity_types",
                company.get("activity_type"),
            )
        )

        if not title:
            errors.append(
                "Firma unvanı bulunmuyor."
            )

        if len(tax_number) not in {10, 11}:
            errors.append(
                "VKN 10, TCKN 11 haneli olmalıdır."
            )

        if not activity_types:
            errors.append(
                "En az bir faaliyet türü seçilmelidir."
            )

        if not company.get("sector"):
            warnings.append(
                "Firma sektörü henüz belirtilmedi."
            )

        if not company.get("nace_codes"):
            warnings.append(
                "NACE kodu henüz belirtilmedi."
            )

        return {
            "is_valid": not errors,
            "errors": errors,
            "warnings": warnings,
        }
    
    def validate_company_profile(
        self,
        company_or_id,
    ) -> dict:
        """
        Eski servislerle uyumluluk için firma profilini doğrular.
        """

        return self.validate_profile(
            company_or_id
        )
    
    def determine_document_direction(
        self,
        company_id: str,
        invoice_data: dict,
    ) -> str | None:
        """
        Aktif firmanın faturadaki satıcı veya alıcı
        olmasına göre alış/satış yönünü belirler.
        """

        company = self.find_company(company_id)

        if not company:
            return None

        company_tax_number = (
            self._normalize_tax_number(
                company.get("tax_number", "")
            )
        )

        seller_tax_number = (
            self._normalize_tax_number(
                invoice_data.get(
                    "seller_tax_number",
                    "",
                )
            )
        )

        buyer_tax_number = (
            self._normalize_tax_number(
                invoice_data.get(
                    "buyer_tax_number",
                    "",
                )
            )
        )

        if (
            company_tax_number
            and company_tax_number
            == seller_tax_number
        ):
            return "sale"

        if (
            company_tax_number
            and company_tax_number
            == buyer_tax_number
        ):
            return "purchase"

        return None

    def _ensure_storage(self):
        """
        Veri dosyası yoksa başlangıç dosyasını oluşturur.
        """

        self.data_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.data_file.exists():
            self._save_data({
                "metadata": {
                    "name": "MarkaAI Firma Profilleri",
                    "version": "0.2.0",
                    "last_updated": (
                        datetime.now().date().isoformat()
                    ),
                    "description": (
                        "MarkaAI kayıtlı firma profilleri."
                    ),
                },
                "companies": [],
            })

    def _load_data(self) -> dict:
        try:
            with self.data_file.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

        except json.JSONDecodeError as error:
            raise ValueError(
                "Firma profilleri JSON dosyası bozuk."
            ) from error

        if not isinstance(data, dict):
            raise ValueError(
                "Firma profilleri dosyası geçerli değil."
            )

        data.setdefault("metadata", {})
        data.setdefault("companies", [])

        for company in data["companies"]:
            self._migrate_company(company)

        return data

    def _save_data(
        self,
        data: dict,
    ):
        data.setdefault("metadata", {})
        data.setdefault("companies", [])

        data["metadata"]["last_updated"] = (
            datetime.now().date().isoformat()
        )

        temporary_file = self.data_file.with_suffix(
            ".tmp"
        )

        with temporary_file.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2,
            )

        temporary_file.replace(
            self.data_file
        )

    def _migrate_company(
        self,
        company: dict,
    ):
        """
        Eski tek faaliyetli firma kayıtlarını
        çok faaliyetli yeni yapıya uyarlar.
        """

        activity_types = self._normalize_activity_types(
            company.get(
                "activity_types",
                company.get("activity_type"),
            )
        )

        company["activity_types"] = activity_types

        if not company.get(
            "primary_activity_type"
        ):
            company["primary_activity_type"] = (
                activity_types[0]
                if activity_types
                else ""
            )

        company["activity_type"] = company.get(
            "primary_activity_type",
            "",
        )

        company.setdefault(
            "license_active",
            True,
        )

    def _validate_required_fields(
        self,
        *,
        title: str,
        tax_number: str,
        activity_types: list[str],
        primary_activity_type: str,
    ):
        if not title:
            raise ValueError(
                "Firma unvanı boş bırakılamaz."
            )

        if len(tax_number) not in {10, 11}:
            raise ValueError(
                "VKN 10, TCKN 11 haneli olmalıdır."
            )

        if not activity_types:
            raise ValueError(
                "En az bir faaliyet türü seçilmelidir."
            )

        invalid_types = [
            activity_type
            for activity_type in activity_types
            if activity_type
            not in self.ALLOWED_ACTIVITY_TYPES
        ]

        if invalid_types:
            raise ValueError(
                "Geçersiz faaliyet türleri: "
                + ", ".join(invalid_types)
            )

        if (
            primary_activity_type
            not in activity_types
        ):
            raise ValueError(
                "Ana faaliyet türü, seçilen faaliyetler "
                "arasında olmalıdır."
            )

    def _normalize_activity_types(
        self,
        activity_types,
    ) -> list[str]:
        if activity_types is None:
            return []

        if isinstance(activity_types, str):
            values = re.split(
                r"[,;/|]",
                activity_types,
            )
        elif isinstance(
            activity_types,
            (list, tuple, set),
        ):
            values = activity_types
        else:
            values = [activity_types]

        normalized = []

        for value in values:
            activity_type = str(
                value
            ).strip().casefold()

            if (
                activity_type
                and activity_type
                not in normalized
            ):
                normalized.append(
                    activity_type
                )

        return normalized

    def _normalize_tax_number(
        self,
        tax_number,
    ) -> str:
        return re.sub(
            r"\D",
            "",
            str(tax_number or ""),
        )

    def _normalize_list(
        self,
        value,
    ) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            values = re.split(
                r"[,;/|]",
                value,
            )
        elif isinstance(
            value,
            (list, tuple, set),
        ):
            values = value
        else:
            values = [value]

        normalized = []

        for item in values:
            text = str(item).strip()

            if text and text not in normalized:
                normalized.append(text)

        return normalized

    def _generate_company_id(
        self,
        tax_number: str,
    ) -> str:
        short_id = uuid4().hex[:6]

        return (
            f"company_{tax_number}_{short_id}"
        )

    def _has_inventory_activity(
        self,
        activity_types: list[str],
    ) -> bool:
        inventory_activities = {
            "manufacturing",
            "trading",
            "import",
            "export",
        }

        return bool(
            inventory_activities.intersection(
                activity_types
            )
        )

    def _build_default_purchase_accounts(
        self,
        activity_types: list[str],
    ) -> dict:
        accounts = {
            "fixed_asset": "255",
            "administrative_expense": "770",
            "selling_expense": "760",
        }

        if "manufacturing" in activity_types:
            accounts.update({
                "raw_material": "150",
                "trade_goods": "153",
                "service_cost": "740",
            })

        if "trading" in activity_types:
            accounts["trade_goods"] = "153"

        if "service" in activity_types:
            accounts.update({
                "direct_service_cost": "740",
                "service_cost": "740",
            })

        if (
            "import" in activity_types
            or "export" in activity_types
        ):
            accounts.setdefault(
                "trade_goods",
                "153",
            )

        return accounts

    def _build_learning_settings(
        self,
        supplied_settings,
    ) -> dict:
        settings = {
            "enabled": True,
            "minimum_approved_examples": 5,
            "maximum_confidence_from_history": 95,
            "requires_professional_approval": True,
        }

        if isinstance(
            supplied_settings,
            dict,
        ):
            settings.update(
                supplied_settings
            )

        return settings