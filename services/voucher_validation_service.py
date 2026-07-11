import re
from decimal import Decimal, InvalidOperation

from services.accounting_knowledge_service import (
    AccountingKnowledgeService,
)


class VoucherValidationService:
    """
    Önerilen muhasebe fişini temel muhasebe ve veri kurallarıyla doğrular.

    Bu servis:
    - Kesin kayıt oluşturmaz.
    - Vergisel uygunluğa kesin hüküm vermez.
    - Hataları ve uyarıları kullanıcıya bildirir.
    - Mali müşavir onayı olmadan aktarımı engeller.
    """

    def __init__(self):
        self.knowledge_service = AccountingKnowledgeService()

    def validate(
        self,
        invoice_data: dict,
        accounting_data: dict,
        user_approved: bool = False,
    ) -> dict:
        """
        Fatura ve muhasebe önerisini kontrol eder.

        Sonuç örneği:
        {
            "is_valid": False,
            "can_export": False,
            "errors": [],
            "warnings": [],
            "checks": []
        }
        """

        errors = []
        warnings = []
        checks = []

        debit_entries = accounting_data.get(
            "debit_entries",
            [],
        )
        credit_entries = accounting_data.get(
            "credit_entries",
            [],
        )

        self._validate_invoice_number(
            invoice_data,
            errors,
            checks,
        )

        self._validate_invoice_date(
            invoice_data,
            errors,
            checks,
        )

        self._validate_supplier(
            invoice_data,
            warnings,
            checks,
        )

        self._validate_accounts_exist(
            debit_entries,
            credit_entries,
            errors,
            checks,
        )

        self._validate_entry_sides(
            debit_entries,
            credit_entries,
            errors,
            checks,
        )

        debit_total = self._calculate_total(
            debit_entries,
            errors,
            "Borç",
        )

        credit_total = self._calculate_total(
            credit_entries,
            errors,
            "Alacak",
        )

        self._validate_balance(
            debit_total,
            credit_total,
            errors,
            checks,
        )

        self._validate_purchase_vat(
            invoice_data,
            debit_entries,
            warnings,
            checks,
        )

        self._validate_trade_payable(
            invoice_data,
            credit_entries,
            warnings,
            checks,
        )

        self._validate_required_confirmation(
            user_approved,
            errors,
            checks,
        )

        service_warnings = accounting_data.get(
            "warnings",
            [],
        )

        for warning in service_warnings:
            if warning not in warnings:
                warnings.append(warning)

        is_valid = len(errors) == 0

        return {
            "is_valid": is_valid,
            "can_export": is_valid and user_approved,
            "errors": errors,
            "warnings": warnings,
            "checks": checks,
            "debit_total": self._format_decimal(
                debit_total
            ),
            "credit_total": self._format_decimal(
                credit_total
            ),
            "user_approved": user_approved,
        }

    def _validate_invoice_number(
        self,
        invoice_data: dict,
        errors: list[str],
        checks: list[dict],
    ):
        invoice_number = str(
            invoice_data.get("invoice_number", "")
        ).strip()

        passed = invoice_number not in {
            "",
            "-",
            "None",
        }

        checks.append({
            "code": "V002",
            "name": "Belge numarası kontrolü",
            "passed": passed,
        })

        if not passed:
            errors.append(
                "Fatura numarası bulunamadı. "
                "Fiş kesinleştirilemez."
            )

    def _validate_invoice_date(
        self,
        invoice_data: dict,
        errors: list[str],
        checks: list[dict],
    ):
        invoice_date = str(
            invoice_data.get("invoice_date", "")
        ).strip()

        date_pattern = (
            r"^\d{1,2}[-./]\d{1,2}[-./]\d{4}$"
        )

        passed = bool(
            re.match(date_pattern, invoice_date)
        )

        checks.append({
            "code": "V003",
            "name": "Belge tarihi kontrolü",
            "passed": passed,
        })

        if not passed:
            errors.append(
                "Fatura tarihi bulunamadı veya "
                "beklenen biçimde değil."
            )

    def _validate_supplier(
        self,
        invoice_data: dict,
        warnings: list[str],
        checks: list[dict],
    ):
        seller_tax_number = str(
            invoice_data.get(
                "seller_tax_number",
                "",
            )
        ).strip()

        passed = (
            seller_tax_number.isdigit()
            and len(seller_tax_number) in {10, 11}
        )

        checks.append({
            "code": "SUPPLIER",
            "name": "Satıcı VKN/TCKN kontrolü",
            "passed": passed,
        })

        if not passed:
            warnings.append(
                "Satıcı VKN/TCKN bilgisi doğrulanamadı."
            )

    def _validate_accounts_exist(
        self,
        debit_entries: list[dict],
        credit_entries: list[dict],
        errors: list[str],
        checks: list[dict],
    ):
        missing_accounts = []

        for entry in debit_entries + credit_entries:
            account_code = str(
                entry.get("account_code", "")
            ).strip()

            if not self.knowledge_service.account_exists(
                account_code
            ):
                missing_accounts.append(account_code)

        passed = len(missing_accounts) == 0

        checks.append({
            "code": "ACCOUNT_EXISTS",
            "name": "Hesap bilgi tabanı kontrolü",
            "passed": passed,
        })

        if missing_accounts:
            errors.append(
                "Bilgi tabanında bulunmayan hesaplar var: "
                + ", ".join(missing_accounts)
            )

    def _validate_entry_sides(
        self,
        debit_entries: list[dict],
        credit_entries: list[dict],
        errors: list[str],
        checks: list[dict],
    ):
        passed = bool(
            debit_entries and credit_entries
        )

        checks.append({
            "code": "ENTRY_SIDES",
            "name": "Borç ve alacak satırları kontrolü",
            "passed": passed,
        })

        if not debit_entries:
            errors.append(
                "Fişte borç kaydı bulunmuyor."
            )

        if not credit_entries:
            errors.append(
                "Fişte alacak kaydı bulunmuyor."
            )

    def _calculate_total(
        self,
        entries: list[dict],
        errors: list[str],
        side_name: str,
    ) -> Decimal:
        total = Decimal("0")

        for index, entry in enumerate(
            entries,
            start=1,
        ):
            amount = entry.get("amount", "-")

            try:
                total += self._parse_amount(amount)

            except ValueError:
                errors.append(
                    f"{side_name} tarafındaki "
                    f"{index}. satırın tutarı geçersiz: "
                    f"{amount}"
                )

        return total

    def _validate_balance(
        self,
        debit_total: Decimal,
        credit_total: Decimal,
        errors: list[str],
        checks: list[dict],
    ):
        passed = debit_total == credit_total

        checks.append({
            "code": "V001",
            "name": "Borç alacak eşitliği",
            "passed": passed,
        })

        if not passed:
            errors.append(
                "Borç ve alacak toplamları eşit değil. "
                f"Borç: {self._format_decimal(debit_total)}, "
                f"Alacak: {self._format_decimal(credit_total)}"
            )

    def _validate_purchase_vat(
        self,
        invoice_data: dict,
        debit_entries: list[dict],
        warnings: list[str],
        checks: list[dict],
    ):
        vat_amount = invoice_data.get(
            "vat_amount",
            "-",
        )

        has_vat_amount = self._is_positive_amount(
            vat_amount
        )

        has_191_account = any(
            str(entry.get("account_code")) == "191"
            for entry in debit_entries
        )

        passed = (
            not has_vat_amount
            or has_191_account
        )

        checks.append({
            "code": "VAT_191",
            "name": "191 İndirilecek KDV kontrolü",
            "passed": passed,
        })

        if has_vat_amount and not has_191_account:
            warnings.append(
                "Faturada KDV bulunduğu halde "
                "191 İndirilecek KDV hesabı önerilmedi."
            )

        if has_191_account:
            warnings.append(
                "191 hesabındaki KDV'nin indirim şartları, "
                "belgenin niteliği ve mevzuat hükümleri "
                "ayrıca kontrol edilmelidir."
            )

    def _validate_trade_payable(
        self,
        invoice_data: dict,
        credit_entries: list[dict],
        warnings: list[str],
        checks: list[dict],
    ):
        has_320_account = any(
            str(entry.get("account_code")) == "320"
            for entry in credit_entries
        )

        seller_tax_number = str(
            invoice_data.get(
                "seller_tax_number",
                "",
            )
        ).strip()

        supplier_exists = (
            seller_tax_number.isdigit()
            and len(seller_tax_number) in {10, 11}
        )

        passed = (
            not has_320_account
            or supplier_exists
        )

        checks.append({
            "code": "PAYABLE_320",
            "name": "320 Satıcılar kontrolü",
            "passed": passed,
        })

        if has_320_account and not supplier_exists:
            warnings.append(
                "320 Satıcılar hesabı önerildi ancak "
                "satıcı VKN/TCKN bilgisi doğrulanamadı."
            )

    def _validate_required_confirmation(
        self,
        user_approved: bool,
        errors: list[str],
        checks: list[dict],
    ):
        checks.append({
            "code": "V006",
            "name": "Mali müşavir onayı",
            "passed": user_approved,
        })

        if not user_approved:
            errors.append(
                "Mali müşavir onayı verilmediği için "
                "fiş kesinleştirilemez veya aktarılamaz."
            )

    def _parse_amount(self, amount) -> Decimal:
        """
        Türkçe para biçimini Decimal değerine dönüştürür.

        Örnek:
        17.600,00 TL -> Decimal('17600.00')
        """

        if amount is None:
            raise ValueError(
                "Tutar boş olamaz."
            )

        normalized = str(amount).strip()

        normalized = (
            normalized
            .replace("TL", "")
            .replace("₺", "")
            .replace(" ", "")
            .replace(".", "")
            .replace(",", ".")
        )

        if normalized in {
            "",
            "-",
        }:
            raise ValueError(
                "Geçersiz tutar."
            )

        try:
            return Decimal(normalized)

        except InvalidOperation as error:
            raise ValueError(
                f"Tutar dönüştürülemedi: {amount}"
            ) from error

    def _is_positive_amount(self, amount) -> bool:
        try:
            return self._parse_amount(amount) > 0

        except ValueError:
            return False

    def _format_decimal(
        self,
        amount: Decimal,
    ) -> str:
        formatted = f"{amount:,.2f}"

        formatted = (
            formatted
            .replace(",", "_")
            .replace(".", ",")
            .replace("_", ".")
        )

        return f"{formatted} TL"