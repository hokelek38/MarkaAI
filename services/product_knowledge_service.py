import json
from pathlib import Path


class ProductKnowledgeService:
    """
    Ürün ve hizmet bilgi tabanını okur.

    Bu servis:
    - Ürün veya hizmet eşleşmelerini bulur.
    - Firma faaliyet türüne uygun kullanım seçeneklerini getirir.
    - Tek başına muhasebe kaydı oluşturmaz.
    """

    def __init__(self):
        project_root = Path(__file__).resolve().parent.parent

        self.catalog_file = (
            project_root
            / "data"
            / "products"
            / "product_catalog.json"
        )

        self.catalog_data = self._load_catalog()
        self.items = self.catalog_data.get("items", [])

    def _load_catalog(self) -> dict:
        """
        Ürün kataloğunu JSON dosyasından okur.
        """

        if not self.catalog_file.exists():
            raise FileNotFoundError(
                "Ürün bilgi tabanı bulunamadı:\n"
                f"{self.catalog_file}"
            )

        try:
            with self.catalog_file.open(
                "r",
                encoding="utf-8",
            ) as file:
                return json.load(file)

        except json.JSONDecodeError as error:
            raise ValueError(
                "Ürün bilgi tabanı geçerli JSON biçiminde değil.\n"
                f"Satır: {error.lineno}, sütun: {error.colno}\n"
                f"Detay: {error.msg}"
            ) from error

    def get_metadata(self) -> dict:
        """
        Ürün bilgi tabanının sürüm bilgisini döndürür.
        """

        return self.catalog_data.get("metadata", {}).copy()

    def get_all_items(self) -> list[dict]:
        """
        Bütün ürün ve hizmet kayıtlarını döndürür.
        """

        return [
            item.copy()
            for item in self.items
        ]

    def get_item_by_id(
        self,
        product_id: str,
    ) -> dict | None:
        """
        Ürün kimliğine göre kayıt döndürür.
        """

        normalized_id = str(product_id).strip()

        for item in self.items:
            if item.get("product_id") == normalized_id:
                return item.copy()

        return None

    def find_matches(
        self,
        text: str,
    ) -> list[dict]:
        """
        Verilen metinde geçen ürün veya hizmetleri bulur.
        """

        normalized_text = str(text).casefold()
        matches = []

        for item in self.items:
            keywords = item.get("keywords", [])

            matched_keywords = [
                keyword
                for keyword in keywords
                if str(keyword).casefold() in normalized_text
            ]

            if matched_keywords:
                match_result = item.copy()
                match_result["matched_keywords"] = matched_keywords
                match_result["match_score"] = len(matched_keywords)
                matches.append(match_result)

        matches.sort(
            key=lambda item: (
                item.get("match_score", 0),
                len(item.get("name", "")),
            ),
            reverse=True,
        )

        return matches

    def find_best_match(
        self,
        text: str,
    ) -> dict | None:
        """
        Metindeki en güçlü ürün veya hizmet eşleşmesini döndürür.
        """

        matches = self.find_matches(text)

        if not matches:
            return None

        return matches[0]

    def get_possible_usages(
        self,
        product_id: str,
        activity_type: str | None = None,
    ) -> list[dict]:
        """
        Ürünün olası kullanım şekillerini döndürür.

        activity_type verilirse yalnızca ilgili firma türüne uygun
        seçenekler gelir.
        """

        item = self.get_item_by_id(product_id)

        if not item:
            return []

        possible_usages = item.get(
            "possible_usages",
            [],
        )

        if not activity_type:
            return [
                usage.copy()
                for usage in possible_usages
            ]

        normalized_activity_type = str(
            activity_type
        ).strip().casefold()

        return [
            usage.copy()
            for usage in possible_usages
            if str(
                usage.get("activity_type", "")
            ).strip().casefold()
            == normalized_activity_type
        ]

    def suggest_usage(
        self,
        text: str,
        activity_type: str,
    ) -> dict:
        """
        Metin ve firma faaliyet türüne göre ürün kullanım amacı önerir.
        """

        best_match = self.find_best_match(text)

        if not best_match:
            return {
                "matched": False,
                "product": None,
                "usage": None,
                "suggested_account": None,
                "confidence": 0,
                "reason": (
                    "Ürün veya hizmet bilgi tabanında eşleşme bulunamadı."
                ),
                "matched_keywords": [],
                "requires_user_confirmation": True,
            }

        possible_usages = self.get_possible_usages(
            best_match["product_id"],
            activity_type,
        )

        if not possible_usages:
            return {
                "matched": True,
                "product": best_match,
                "usage": None,
                "suggested_account": None,
                "confidence": 0,
                "reason": (
                    "Ürün bulundu ancak firmanın faaliyet türüne uygun "
                    "kullanım seçeneği tanımlı değil."
                ),
                "matched_keywords": best_match.get(
                    "matched_keywords",
                    [],
                ),
                "requires_user_confirmation": True,
            }

        best_usage = max(
            possible_usages,
            key=lambda usage: int(
                usage.get("confidence", 0)
            ),
        )

        return {
            "matched": True,
            "product": best_match,
            "usage": best_usage.get("usage"),
            "suggested_account": best_usage.get(
                "suggested_account"
            ),
            "confidence": int(
                best_usage.get("confidence", 0)
            ),
            "reason": best_usage.get(
                "reason",
                "Ürün kullanım amacı önerildi.",
            ),
            "matched_keywords": best_match.get(
                "matched_keywords",
                [],
            ),
            "requires_user_confirmation": (
                best_match.get(
                    "requires_usage_confirmation",
                    True,
                )
            ),
            "requires_fixed_asset_validation": (
                best_match.get(
                    "requires_fixed_asset_validation",
                    False,
                )
            ),
            "requires_allocation": best_match.get(
                "requires_allocation",
                False,
            ),
            "verified": best_match.get(
                "verified",
                False,
            ),
        }

    def validate_catalog(self) -> dict:
        """
        Ürün bilgi tabanındaki yapısal hataları kontrol eder.
        """

        errors = []
        warnings = []
        product_ids = set()

        for index, item in enumerate(
            self.items,
            start=1,
        ):
            product_id = str(
                item.get("product_id", "")
            ).strip()

            if not product_id:
                errors.append(
                    f"{index}. üründe product_id bulunmuyor."
                )

            elif product_id in product_ids:
                errors.append(
                    f"Mükerrer product_id bulundu: {product_id}"
                )

            else:
                product_ids.add(product_id)

            if not item.get("name"):
                errors.append(
                    f"{product_id or index} ürününde ad bulunmuyor."
                )

            keywords = item.get("keywords")

            if not isinstance(keywords, list) or not keywords:
                warnings.append(
                    f"{product_id or index} ürününde anahtar kelime bulunmuyor."
                )

            possible_usages = item.get(
                "possible_usages"
            )

            if (
                not isinstance(possible_usages, list)
                or not possible_usages
            ):
                errors.append(
                    f"{product_id or index} ürününde kullanım seçeneği bulunmuyor."
                )
                continue

            for usage_index, usage in enumerate(
                possible_usages,
                start=1,
            ):
                if not usage.get("activity_type"):
                    errors.append(
                        f"{product_id} ürününün "
                        f"{usage_index}. kullanımında activity_type yok."
                    )

                if not usage.get("usage"):
                    errors.append(
                        f"{product_id} ürününün "
                        f"{usage_index}. kullanımında usage yok."
                    )

                if not usage.get("suggested_account"):
                    errors.append(
                        f"{product_id} ürününün "
                        f"{usage_index}. kullanımında hesap yok."
                    )

                confidence = usage.get("confidence")

                if not isinstance(confidence, int):
                    errors.append(
                        f"{product_id} ürününün "
                        f"{usage_index}. kullanımında güven oranı tam sayı değil."
                    )

                elif not 0 <= confidence <= 100:
                    errors.append(
                        f"{product_id} ürününün "
                        f"{usage_index}. kullanımında güven oranı geçersiz."
                    )

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "item_count": len(self.items),
        }