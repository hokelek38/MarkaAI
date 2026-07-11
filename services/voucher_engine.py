from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4


class VoucherEngine:
    """
    MarkaAI Standard Voucher (MSV) oluşturma motoru.

    Görevleri:
    - Muhasebe servislerinden gelen borç/alacak satırlarını standartlaştırmak
    - Fiş toplamlarını hesaplamak
    - Borç/alacak eşitliğini kontrol etmek
    - Taslak fiş oluşturmak
    - Kullanıcı onayını kaydetmek
    - ERP aktarım durumunu takip etmek

    Bu servis muhasebe hesabı seçmez ve vergi hesaplaması yapmaz.
    """

    SCHEMA_NAME = "MarkaAI Standard Voucher"
    SCHEMA_VERSION = "1.0"

    def create_voucher(
        self,
        *,
        voucher_type: str,
        company: dict,
        document: dict,
        transaction: dict,
        debit_entries: list[dict],
        credit_entries: list[dict],
        decision: dict,
        tax_information: dict | None = None,
        explanation: str = "",
        created_by: str = "system",
    ) -> dict:
        """
        Verilen muhasebe satırlarından taslak MSV fişi oluşturur.
        """

        if not isinstance(debit_entries, list):
            raise TypeError(
                "debit_entries bir liste olmalıdır."
            )

        if not isinstance(credit_entries, list):
            raise TypeError(
                "credit_entries bir liste olmalıdır."
            )

        lines = self._build_lines(
            debit_entries=debit_entries,
            credit_entries=credit_entries,
        )

        totals = self._calculate_totals(lines)

        voucher_id = self._generate_voucher_id()

        created_at = datetime.now().isoformat(
            timespec="seconds"
        )

        return {
            "schema": self.SCHEMA_NAME,
            "schema_version": self.SCHEMA_VERSION,
            "voucher": {
                "voucher_id": voucher_id,
                "voucher_type": str(voucher_type).strip(),
                "voucher_date": document.get(
                    "voucher_date",
                    document.get(
                        "document_date",
                        document.get(
                            "invoice_date",
                            "",
                        ),
                    ),
                ),
                "document": {
                    "document_number": document.get(
                        "document_number",
                        document.get(
                            "invoice_number",
                            "",
                        ),
                    ),
                    "document_date": document.get(
                        "document_date",
                        document.get(
                            "invoice_date",
                            "",
                        ),
                    ),
                    "document_type": document.get(
                        "document_type",
                        "",
                    ),
                    "ettn": document.get(
                        "ettn",
                        "",
                    ),
                    "source_file": document.get(
                        "source_file",
                        document.get(
                            "file_name",
                            "",
                        ),
                    ),
                    "source_file_path": document.get(
                        "source_file_path",
                        "",
                    ),
                    "original_document_number": document.get(
                        "original_document_number",
                        "",
                    ),
                },
                "company": {
                    "company_id": company.get(
                        "company_id",
                        "",
                    ),
                    "title": company.get(
                        "title",
                        "",
                    ),
                    "tax_number": company.get(
                        "tax_number",
                        "",
                    ),
                },
                "counterparty": {
                    "title": document.get(
                        "counterparty_title",
                        "",
                    ),
                    "tax_number": document.get(
                        "counterparty_tax_number",
                        "",
                    ),
                    "role": document.get(
                        "counterparty_role",
                        "",
                    ),
                },
                "transaction": {
                    "transaction_code": transaction.get(
                        "transaction_code",
                        "",
                    ),
                    "transaction_name": transaction.get(
                        "transaction_name",
                        "",
                    ),
                    "direction": transaction.get(
                        "direction",
                        "",
                    ),
                    "tax_scenario": transaction.get(
                        "tax_scenario",
                        "",
                    ),
                    "currency": transaction.get(
                        "currency",
                        "TRY",
                    ),
                    "exchange_rate": self._decimal_to_string(
                        self._to_decimal(
                            transaction.get(
                                "exchange_rate",
                                "1",
                            )
                        )
                    ),
                },
                "totals": {
                    "debit_total": self._decimal_to_string(
                        totals["debit_total"]
                    ),
                    "credit_total": self._decimal_to_string(
                        totals["credit_total"]
                    ),
                    "difference": self._decimal_to_string(
                        totals["difference"]
                    ),
                    "is_balanced": totals["is_balanced"],
                },
                "tax_information": self._normalize_tax_information(
                    tax_information or {}
                ),
                "lines": lines,
                "explanation": str(
                    explanation or ""
                ),
                "decision": {
                    "confidence": int(
                        decision.get(
                            "confidence",
                            0,
                        )
                        or 0
                    ),
                    "rule_id": decision.get(
                        "rule_id",
                        decision.get(
                            "applied_rule_id",
                            "",
                        ),
                    ),
                    "reason": decision.get(
                        "reason",
                        "",
                    ),
                    "warnings": list(
                        decision.get(
                            "warnings",
                            [],
                        )
                    ),
                    "requires_approval": True,
                    "approved": False,
                    "approved_by": None,
                    "approved_at": None,
                },
                "audit": {
                    "created_at": created_at,
                    "created_by": created_by,
                    "updated_at": created_at,
                    "updated_by": created_by,
                    "source": "MarkaAI",
                    "status": "draft",
                },
                "integration": {
                    "exported": False,
                    "exported_system": None,
                    "exported_at": None,
                    "external_reference": None,
                    "export_errors": [],
                },
            },
        }

    def approve_voucher(
        self,
        voucher_data: dict,
        approved_by: str,
    ) -> dict:
        """
        Dengeli taslak fişi kullanıcı onayıyla onaylar.
        """

        voucher = self._get_voucher(voucher_data)

        if not str(approved_by).strip():
            raise ValueError(
                "Onaylayan kullanıcı bilgisi boş olamaz."
            )

        if (
            voucher.get("totals", {}).get(
                "is_balanced"
            )
            is not True
        ):
            raise ValueError(
                "Borç ve alacak toplamları eşit olmayan fiş onaylanamaz."
            )

        if not voucher.get("lines"):
            raise ValueError(
                "Muhasebe satırı bulunmayan fiş onaylanamaz."
            )

        approved_at = datetime.now().isoformat(
            timespec="seconds"
        )

        voucher["decision"]["approved"] = True
        voucher["decision"]["approved_by"] = (
            approved_by
        )
        voucher["decision"]["approved_at"] = (
            approved_at
        )

        voucher["audit"]["status"] = "approved"
        voucher["audit"]["updated_at"] = approved_at
        voucher["audit"]["updated_by"] = approved_by

        return voucher_data

    def revoke_approval(
        self,
        voucher_data: dict,
        revoked_by: str,
    ) -> dict:
        """
        Henüz dış sisteme aktarılmamış fişin onayını kaldırır.
        """

        voucher = self._get_voucher(voucher_data)

        if (
            voucher.get("integration", {}).get(
                "exported"
            )
            is True
        ):
            raise ValueError(
                "Dış sisteme aktarılmış fişin onayı kaldırılamaz."
            )

        updated_at = datetime.now().isoformat(
            timespec="seconds"
        )

        voucher["decision"]["approved"] = False
        voucher["decision"]["approved_by"] = None
        voucher["decision"]["approved_at"] = None

        voucher["audit"]["status"] = "draft"
        voucher["audit"]["updated_at"] = updated_at
        voucher["audit"]["updated_by"] = revoked_by

        return voucher_data

    def mark_as_exported(
        self,
        voucher_data: dict,
        target_system: str,
        external_reference: str | None = None,
    ) -> dict:
        """
        Onaylı fişi dış sisteme aktarılmış olarak işaretler.
        """

        voucher = self._get_voucher(voucher_data)

        if (
            voucher.get("decision", {}).get(
                "approved"
            )
            is not True
        ):
            raise ValueError(
                "Onaylanmamış fiş dış sisteme aktarılamaz."
            )

        if (
            voucher.get("totals", {}).get(
                "is_balanced"
            )
            is not True
        ):
            raise ValueError(
                "Borç ve alacak toplamları eşit olmayan fiş aktarılamaz."
            )

        if not str(target_system).strip():
            raise ValueError(
                "Hedef sistem adı boş olamaz."
            )

        exported_at = datetime.now().isoformat(
            timespec="seconds"
        )

        voucher["integration"]["exported"] = True
        voucher["integration"]["exported_system"] = (
            target_system
        )
        voucher["integration"]["exported_at"] = (
            exported_at
        )
        voucher["integration"]["external_reference"] = (
            external_reference
        )

        voucher["audit"]["status"] = "exported"
        voucher["audit"]["updated_at"] = exported_at

        return voucher_data

    def add_export_error(
        self,
        voucher_data: dict,
        target_system: str,
        error_message: str,
    ) -> dict:
        """
        ERP aktarımında oluşan hatayı fişin denetim kaydına ekler.
        """

        voucher = self._get_voucher(voucher_data)

        voucher["integration"].setdefault(
            "export_errors",
            [],
        )

        voucher["integration"]["export_errors"].append({
            "target_system": target_system,
            "message": error_message,
            "created_at": datetime.now().isoformat(
                timespec="seconds"
            ),
        })

        voucher["audit"]["status"] = "export_failed"
        voucher["audit"]["updated_at"] = (
            datetime.now().isoformat(
                timespec="seconds"
            )
        )

        return voucher_data

    def recalculate_totals(
        self,
        voucher_data: dict,
    ) -> dict:
        """
        Fiş satırları değiştirildikten sonra toplamları yeniden hesaplar.
        """

        voucher = self._get_voucher(voucher_data)

        totals = self._calculate_totals(
            voucher.get("lines", [])
        )

        voucher["totals"] = {
            "debit_total": self._decimal_to_string(
                totals["debit_total"]
            ),
            "credit_total": self._decimal_to_string(
                totals["credit_total"]
            ),
            "difference": self._decimal_to_string(
                totals["difference"]
            ),
            "is_balanced": totals["is_balanced"],
        }

        voucher["audit"]["updated_at"] = (
            datetime.now().isoformat(
                timespec="seconds"
            )
        )

        return voucher_data

    def _build_lines(
        self,
        debit_entries: list[dict],
        credit_entries: list[dict],
    ) -> list[dict]:
        """
        Borç ve alacak kayıtlarını standart MSV satırlarına dönüştürür.
        """

        lines = []
        line_number = 1

        for entry in debit_entries:
            lines.append(
                self._create_line(
                    line_number=line_number,
                    entry=entry,
                    side="debit",
                )
            )
            line_number += 1

        for entry in credit_entries:
            lines.append(
                self._create_line(
                    line_number=line_number,
                    entry=entry,
                    side="credit",
                )
            )
            line_number += 1

        return lines

    def _create_line(
        self,
        *,
        line_number: int,
        entry: dict,
        side: str,
    ) -> dict:
        """
        Tek muhasebe satırını ortak MSV biçimine dönüştürür.
        """

        if side == "debit":
            debit = self._extract_amount(
                entry=entry,
                preferred_fields=[
                    "debit_raw",
                    "debit",
                    "amount",
                ],
            )
            credit = Decimal("0.00")

        elif side == "credit":
            debit = Decimal("0.00")
            credit = self._extract_amount(
                entry=entry,
                preferred_fields=[
                    "credit_raw",
                    "credit",
                    "amount",
                ],
            )

        else:
            raise ValueError(
                f"Geçersiz muhasebe tarafı: {side}"
            )

        account_code = str(
            entry.get(
                "account_code",
                "",
            )
        ).strip()

        if not account_code:
            raise ValueError(
                f"{line_number}. satırda hesap kodu bulunmuyor."
            )

        if debit < 0 or credit < 0:
            raise ValueError(
                f"{line_number}. satırda negatif tutar kullanılamaz."
            )

        return {
            "line_number": line_number,
            "account_code": account_code,
            "account_name": entry.get(
                "account_name",
                "",
            ),
            "debit": self._decimal_to_string(
                debit
            ),
            "credit": self._decimal_to_string(
                credit
            ),
            "description": entry.get(
                "description",
                "",
            ),
            "source": entry.get(
                "source",
                "Decision Engine",
            ),
            "verified": bool(
                entry.get(
                    "verified",
                    False,
                )
            ),
            "cost_center": entry.get(
                "cost_center",
                "",
            ),
            "project_code": entry.get(
                "project_code",
                "",
            ),
            "branch_code": entry.get(
                "branch_code",
                "",
            ),
            "reference": entry.get(
                "reference",
                "",
            ),
            "currency": entry.get(
                "currency",
                "TRY",
            ),
            "exchange_rate": self._decimal_to_string(
                self._to_decimal(
                    entry.get(
                        "exchange_rate",
                        "1",
                    )
                )
            ),
        }

    def _calculate_totals(
        self,
        lines: list[dict],
    ) -> dict:
        """
        Fiş satırlarının borç ve alacak toplamlarını hesaplar.
        """

        debit_total = sum(
            (
                self._to_decimal(
                    line.get(
                        "debit",
                        "0",
                    )
                )
                for line in lines
            ),
            Decimal("0.00"),
        )

        credit_total = sum(
            (
                self._to_decimal(
                    line.get(
                        "credit",
                        "0",
                    )
                )
                for line in lines
            ),
            Decimal("0.00"),
        )

        difference = (
            debit_total - credit_total
        ).copy_abs()

        return {
            "debit_total": debit_total,
            "credit_total": credit_total,
            "difference": difference,
            "is_balanced": (
                difference <= Decimal("0.01")
            ),
        }

    def _extract_amount(
        self,
        *,
        entry: dict,
        preferred_fields: list[str],
    ) -> Decimal:
        """
        Muhasebe satırındaki ilk geçerli tutar alanını döndürür.
        """

        for field_name in preferred_fields:
            value = entry.get(field_name)

            if value not in {
                None,
                "",
                "-",
            }:
                return self._to_decimal(value)

        return Decimal("0.00")

    def _normalize_tax_information(
        self,
        tax_information: dict,
    ) -> dict:
        """
        Decimal değerleri JSON uyumlu metinlere dönüştürür.
        """

        normalized = {}

        for key, value in tax_information.items():
            if isinstance(value, Decimal):
                normalized[key] = (
                    self._decimal_to_string(value)
                )

            elif isinstance(value, dict):
                normalized[key] = (
                    self._normalize_tax_information(
                        value
                    )
                )

            elif isinstance(value, list):
                normalized[key] = [
                    self._normalize_tax_value(item)
                    for item in value
                ]

            else:
                normalized[key] = value

        return normalized

    def _normalize_tax_value(self, value):
        if isinstance(value, Decimal):
            return self._decimal_to_string(value)

        if isinstance(value, dict):
            return self._normalize_tax_information(
                value
            )

        return value

    def _to_decimal(
        self,
        value,
    ) -> Decimal:
        """
        Türkçe ve standart sayı biçimlerini Decimal'e dönüştürür.

        Desteklenen örnekler:
        17.600,00 TL -> 17600.00
        17600.00     -> 17600.00
        17600        -> 17600.00
        Decimal      -> Aynı değer
        """

        if isinstance(value, Decimal):
            return value

        if isinstance(value, int):
            return Decimal(value)

        if isinstance(value, float):
            return Decimal(str(value))

        normalized = (
            str(value)
            .replace("TL", "")
            .replace("₺", "")
            .replace(" ", "")
            .strip()
        )

        if normalized in {
            "",
            "-",
            "None",
        }:
            return Decimal("0.00")

        # Türkçe sayı biçimi:
        # 17.600,00 -> 17600.00
        if "," in normalized:
            normalized = (
                normalized
                .replace(".", "")
                .replace(",", ".")
            )

        try:
            return Decimal(normalized)

        except InvalidOperation as error:
            raise ValueError(
                f"Geçersiz tutar: {value}"
            ) from error

    def _decimal_to_string(
        self,
        amount: Decimal,
    ) -> str:
        """
        Decimal değerini ERP aktarımına uygun standart metne dönüştürür.
        """

        return format(
            amount.quantize(
                Decimal("0.01")
            ),
            ".2f",
        )

    def _generate_voucher_id(self) -> str:
        """
        MarkaAI içinde benzersiz fiş kimliği oluşturur.
        """

        timestamp = datetime.now().strftime(
            "%Y%m%d-%H%M%S"
        )

        short_id = uuid4().hex[:8].upper()

        return f"MSV-{timestamp}-{short_id}"

    def _get_voucher(
        self,
        voucher_data: dict,
    ) -> dict:
        """
        MSV nesnesindeki voucher bölümünü güvenli biçimde döndürür.
        """

        if not isinstance(voucher_data, dict):
            raise TypeError(
                "Fiş verisi sözlük biçiminde olmalıdır."
            )

        voucher = voucher_data.get("voucher")

        if not isinstance(voucher, dict):
            raise ValueError(
                "Geçerli bir MSV fişi bulunamadı."
            )

        return voucher