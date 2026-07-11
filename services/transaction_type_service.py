import json
from pathlib import Path


class TransactionTypeService:
    """
    Muhasebe işlem türleri bilgi tabanını okur ve belge senaryolarına
    ilişkin merkezi bilgiler sunar.

    Bu servis:
    - İşlem türlerini yükler.
    - İşlem koduna göre senaryo bilgisi getirir.
    - Zorunlu alanları kontrol eder.
    - Belge verilerinden olası işlem türünü sınıflandırır.
    - Kesin muhasebe kaydı oluşturmaz.
    """

    def __init__(self):
        project_root = Path(__file__).resolve().parent.parent

        self.transaction_file = (
            project_root
            / "data"
            / "accounting"
            / "transaction_types.json"
        )

        self.transaction_data = self._load_transaction_types()
        self.transaction_types = self.transaction_data.get(
            "transaction_types",
            [],
        )

    def _load_transaction_types(self) -> dict:
        """
        İşlem türleri JSON dosyasını okuyup sözlük olarak döndürür.
        """

        if not self.transaction_file.exists():
            raise FileNotFoundError(
                "Muhasebe işlem türleri dosyası bulunamadı:\n"
                f"{self.transaction_file}"
            )

        try:
            with self.transaction_file.open(
                "r",
                encoding="utf-8",
            ) as file:
                return json.load(file)

        except json.JSONDecodeError as error:
            raise ValueError(
                "Muhasebe işlem türleri dosyası geçerli JSON biçiminde değil.\n"
                f"Satır: {error.lineno}, sütun: {error.colno}\n"
                f"Detay: {error.msg}"
            ) from error

    def get_metadata(self) -> dict:
        """
        İşlem türleri bilgi tabanının sürüm bilgilerini döndürür.
        """

        return self.transaction_data.get(
            "metadata",
            {},
        ).copy()

    def get_all_transaction_types(
        self,
        enabled_only: bool = True,
    ) -> list[dict]:
        """
        Bütün işlem türlerini döndürür.

        enabled_only=True ise yalnızca aktif işlem türleri gelir.
        """

        if not enabled_only:
            return [
                transaction.copy()
                for transaction in self.transaction_types
            ]

        return [
            transaction.copy()
            for transaction in self.transaction_types
            if transaction.get("enabled") is True
        ]

    def get_transaction_type(
        self,
        transaction_code: str,
    ) -> dict | None:
        """
        İşlem koduna göre işlem türünü döndürür.
        """

        normalized_code = str(
            transaction_code
        ).strip()

        for transaction in self.transaction_types:
            if (
                transaction.get("transaction_code")
                == normalized_code
            ):
                return transaction.copy()

        return None

    def get_transaction_name(
        self,
        transaction_code: str,
    ) -> str:
        """
        İşlem koduna göre işlem adını döndürür.
        """

        transaction = self.get_transaction_type(
            transaction_code
        )

        if not transaction:
            return "İşlem türü bulunamadı"

        return transaction.get(
            "name",
            "İşlem adı bulunamadı",
        )

    def get_required_fields(
        self,
        transaction_code: str,
    ) -> list[str]:
        """
        İşlem türü için gerekli zorunlu alanları döndürür.
        """

        transaction = self.get_transaction_type(
            transaction_code
        )

        if not transaction:
            return []

        return list(
            transaction.get(
                "required_fields",
                [],
            )
        )

    def get_validation_groups(
        self,
        transaction_code: str,
    ) -> list[str]:
        """
        İşlem türünde çalıştırılması gereken doğrulama gruplarını döndürür.
        """

        transaction = self.get_transaction_type(
            transaction_code
        )

        if not transaction:
            return []

        return list(
            transaction.get(
                "validation_groups",
                [],
            )
        )

    def get_tax_fields(
        self,
        transaction_code: str,
    ) -> dict:
        """
        İşlem türüne ait vergi alanlarını döndürür.
        """

        transaction = self.get_transaction_type(
            transaction_code
        )

        if not transaction:
            return {}

        return transaction.get(
            "tax_fields",
            {},
        ).copy()

    def get_tracking_fields(
        self,
        transaction_code: str,
    ) -> list[str]:
        """
        Süreç boyunca takip edilmesi gereken alanları döndürür.
        """

        transaction = self.get_transaction_type(
            transaction_code
        )

        if not transaction:
            return []

        return list(
            transaction.get(
                "tracking_fields",
                [],
            )
        )

    def validate_required_fields(
        self,
        transaction_code: str,
        document_data: dict,
    ) -> dict:
        """
        İşlem türü için gerekli alanların belgede bulunup bulunmadığını kontrol eder.
        """

        transaction = self.get_transaction_type(
            transaction_code
        )

        if not transaction:
            return {
                "is_valid": False,
                "missing_fields": [],
                "errors": [
                    f"İşlem türü bulunamadı: {transaction_code}"
                ],
            }

        required_fields = transaction.get(
            "required_fields",
            [],
        )

        missing_fields = []

        for field_name in required_fields:
            value = document_data.get(field_name)

            if self._is_empty_value(value):
                missing_fields.append(field_name)

        errors = [
            f"Zorunlu alan eksik: {field_name}"
            for field_name in missing_fields
        ]

        return {
            "is_valid": len(missing_fields) == 0,
            "missing_fields": missing_fields,
            "errors": errors,
        }

    def classify_transaction(
        self,
        document_data: dict,
        document_direction: str | None = None,
    ) -> dict:
        """
        Belge verilerinden olası muhasebe işlem türünü sınıflandırır.

        Bu ilk sürüm kural tabanlıdır.
        Kesin işlem türü kullanıcı tarafından doğrulanmalıdır.
        """

        raw_text = str(
            document_data.get("raw_text", "")
        ).casefold()

        direction = (
            str(document_direction).strip().casefold()
            if document_direction
            else self._detect_direction(document_data)
        )

        candidates = []

        if self._contains_any(
            raw_text,
            [
                "tevkifat",
                "tevkifat oranı",
                "tevkifat kodu",
                "kdv tevkifatı",
            ],
        ):
            if direction == "purchase":
                candidates.append(
                    self._candidate(
                        "WITHHOLDING_PURCHASE",
                        95,
                        "Belgede KDV tevkifatına ilişkin ifadeler bulundu ve işlem yönü alış olarak değerlendirildi.",
                    )
                )

            elif direction == "sale":
                candidates.append(
                    self._candidate(
                        "WITHHOLDING_SALE",
                        95,
                        "Belgede KDV tevkifatına ilişkin ifadeler bulundu ve işlem yönü satış olarak değerlendirildi.",
                    )
                )

        if self._contains_any(
            raw_text,
            [
                "ihraç kayıtlı",
                "ihraç kaydıyla",
                "3065 sayılı kdv kanununun 11/1-c",
                "kdvk 11/1-c",
                "tecil terkin",
                "tecil-terkin",
            ],
        ):
            if direction == "purchase":
                candidates.append(
                    self._candidate(
                        "EXPORT_REGISTERED_PURCHASE",
                        96,
                        "Belgede ihraç kayıtlı teslime ilişkin ifadeler bulundu ve işlem yönü alış olarak değerlendirildi.",
                    )
                )

            elif direction == "sale":
                candidates.append(
                    self._candidate(
                        "EXPORT_REGISTERED_SALE",
                        96,
                        "Belgede ihraç kayıtlı teslime ilişkin ifadeler bulundu ve işlem yönü satış olarak değerlendirildi.",
                    )
                )

        if self._contains_any(
            raw_text,
            [
                "iade faturası",
                "iade",
                "iadeye konu fatura",
                "orijinal fatura",
            ],
        ):
            if direction == "purchase":
                candidates.append(
                    self._candidate(
                        "PURCHASE_RETURN",
                        86,
                        "Belgede iade işlemine ilişkin ifadeler bulundu ve işlem yönü alış tarafı olarak değerlendirildi.",
                    )
                )

            elif direction == "sale":
                candidates.append(
                    self._candidate(
                        "SALES_RETURN",
                        86,
                        "Belgede iade işlemine ilişkin ifadeler bulundu ve işlem yönü satış tarafı olarak değerlendirildi.",
                    )
                )

        if self._contains_any(
            raw_text,
            [
                "gümrük beyannamesi",
                "gümrük tarife",
                "ithalat",
                "ithal edilen",
                "gümrük kıymeti",
                "ithalde alınan kdv",
            ],
        ):
            candidates.append(
                self._candidate(
                    "IMPORT_PURCHASE",
                    92,
                    "Belgede ithalat ve gümrük işlemlerine ilişkin ifadeler bulundu.",
                )
            )

        if self._contains_any(
            raw_text,
            [
                "ihracat faturası",
                "export invoice",
                "gümrük çıkış beyannamesi",
                "yurt dışı satış",
                "fiili ihracat",
            ],
        ):
            candidates.append(
                self._candidate(
                    "DIRECT_EXPORT_SALE",
                    90,
                    "Belgede doğrudan ihracata ilişkin ifadeler bulundu.",
                )
            )

        if self._contains_any(
            raw_text,
            [
                "istisna kodu",
                "kdv istisnası",
                "kdv hesaplanmamıştır",
                "kdv'den istisna",
                "kdvden istisna",
            ],
        ):
            if direction == "purchase":
                candidates.append(
                    self._candidate(
                        "VAT_EXEMPT_PURCHASE",
                        84,
                        "Belgede KDV istisnasına ilişkin ifadeler bulundu ve işlem yönü alış olarak değerlendirildi.",
                    )
                )

            elif direction == "sale":
                candidates.append(
                    self._candidate(
                        "VAT_EXEMPT_SALE",
                        84,
                        "Belgede KDV istisnasına ilişkin ifadeler bulundu ve işlem yönü satış olarak değerlendirildi.",
                    )
                )

        if self._contains_any(
            raw_text,
            [
                "serbest meslek makbuzu",
                "gelir vergisi stopajı",
                "stopaj oranı",
                "stopaj tutarı",
            ],
        ):
            candidates.append(
                self._candidate(
                    "SELF_EMPLOYMENT_WITHHOLDING",
                    93,
                    "Belgede serbest meslek ve gelir vergisi stopajına ilişkin ifadeler bulundu.",
                )
            )

        if not candidates:
            if direction == "sale":
                candidates.append(
                    self._candidate(
                        "STANDARD_SALE",
                        65,
                        "Özel bir vergi senaryosu tespit edilemedi ve işlem satış olarak değerlendirildi.",
                    )
                )

            else:
                candidates.append(
                    self._candidate(
                        "STANDARD_PURCHASE",
                        65,
                        "Özel bir vergi senaryosu tespit edilemedi ve işlem alış olarak değerlendirildi.",
                    )
                )

        candidates.sort(
            key=lambda item: item["confidence"],
            reverse=True,
        )

        selected = candidates[0]

        transaction = self.get_transaction_type(
            selected["transaction_code"]
        )

        return {
            "matched": transaction is not None,
            "transaction_code": selected[
                "transaction_code"
            ],
            "transaction_name": (
                transaction.get("name")
                if transaction
                else "Bilinmeyen işlem türü"
            ),
            "direction": (
                transaction.get("direction")
                if transaction
                else direction
            ),
            "tax_scenario": (
                transaction.get("tax_scenario")
                if transaction
                else None
            ),
            "confidence": selected["confidence"],
            "reason": selected["reason"],
            "candidates": candidates,
            "requires_user_confirmation": True,
        }

    def validate_transaction_database(self) -> dict:
        """
        İşlem türleri bilgi tabanındaki yapısal hataları kontrol eder.
        """

        errors = []
        warnings = []
        transaction_codes = set()

        for index, transaction in enumerate(
            self.transaction_types,
            start=1,
        ):
            transaction_code = str(
                transaction.get("transaction_code", "")
            ).strip()

            if not transaction_code:
                errors.append(
                    f"{index}. işlem türünde transaction_code bulunmuyor."
                )

            elif transaction_code in transaction_codes:
                errors.append(
                    f"Mükerrer işlem kodu bulundu: {transaction_code}"
                )

            else:
                transaction_codes.add(transaction_code)

            if not transaction.get("name"):
                errors.append(
                    f"{transaction_code or index} işleminde ad bulunmuyor."
                )

            if not transaction.get("direction"):
                errors.append(
                    f"{transaction_code or index} işleminde direction bulunmuyor."
                )

            if not transaction.get("tax_scenario"):
                warnings.append(
                    f"{transaction_code or index} işleminde tax_scenario bulunmuyor."
                )

            required_fields = transaction.get(
                "required_fields"
            )

            if not isinstance(required_fields, list):
                errors.append(
                    f"{transaction_code or index} işleminde required_fields liste değil."
                )

            validation_groups = transaction.get(
                "validation_groups"
            )

            if not isinstance(validation_groups, list):
                errors.append(
                    f"{transaction_code or index} işleminde validation_groups liste değil."
                )

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "transaction_count": len(
                self.transaction_types
            ),
        }

    def _detect_direction(
        self,
        document_data: dict,
    ) -> str:
        """
        Belgenin alış veya satış yönünü temel alanlardan tespit etmeye çalışır.
        """

        explicit_direction = str(
            document_data.get("direction", "")
        ).strip().casefold()

        if explicit_direction in {
            "purchase",
            "sale",
        }:
            return explicit_direction

        invoice_type = str(
            document_data.get("invoice_type", "")
        ).strip().casefold()

        if invoice_type in {
            "satis",
            "satış",
            "sale",
        }:
            return "purchase"

        if invoice_type in {
            "alis",
            "alış",
            "purchase",
        }:
            return "purchase"

        return "purchase"

    def _candidate(
        self,
        transaction_code: str,
        confidence: int,
        reason: str,
    ) -> dict:
        return {
            "transaction_code": transaction_code,
            "confidence": confidence,
            "reason": reason,
        }

    def _contains_any(
        self,
        text: str,
        keywords: list[str],
    ) -> bool:
        return any(
            keyword.casefold() in text
            for keyword in keywords
        )

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