import json
from pathlib import Path


class AccountingKnowledgeService:
    """
    Tek Düzen Hesap Planı bilgi tabanını okur ve hesap bilgilerine erişim sağlar.

    Bu servis muhasebe kaydı oluşturmaz.
    Sadece doğrulanmış hesap ve kural bilgilerini diğer servislere sunar.
    """

    def __init__(self):
        project_root = Path(__file__).resolve().parent.parent

        self.knowledge_file = (
            project_root
            / "data"
            / "accounting"
            / "tdhp_accounts.json"
        )

        self.knowledge_base = self._load_knowledge_base()
        self.accounts = self.knowledge_base.get("accounts", [])
        self.validation_rules = self.knowledge_base.get(
            "voucher_validation_rules",
            [],
        )

    def _load_knowledge_base(self) -> dict:
        """
        JSON bilgi tabanını okuyup sözlük olarak döndürür.
        """

        if not self.knowledge_file.exists():
            raise FileNotFoundError(
                "Muhasebe bilgi tabanı bulunamadı:\n"
                f"{self.knowledge_file}"
            )

        try:
            with self.knowledge_file.open(
                "r",
                encoding="utf-8",
            ) as file:
                return json.load(file)

        except json.JSONDecodeError as error:
            raise ValueError(
                "Muhasebe bilgi tabanı geçerli JSON biçiminde değil.\n"
                f"Satır: {error.lineno}, sütun: {error.colno}\n"
                f"Detay: {error.msg}"
            ) from error

    def get_metadata(self) -> dict:
        """
        Bilgi tabanının sürüm ve kaynak bilgilerini döndürür.
        """

        return self.knowledge_base.get("metadata", {})

    def get_all_accounts(self) -> list[dict]:
        """
        Bilgi tabanındaki bütün hesapları döndürür.
        """

        return self.accounts.copy()

    def get_account(self, account_code: str) -> dict | None:
        """
        Hesap koduna göre hesap bilgisi döndürür.

        Örnek:
        get_account("150")
        """

        normalized_code = str(account_code).strip()

        for account in self.accounts:
            if account.get("code") == normalized_code:
                return account.copy()

        return None

    def get_account_name(self, account_code: str) -> str:
        """
        Hesap koduna göre hesap adını döndürür.
        Hesap bulunamazsa güvenli bir açıklama verir.
        """

        account = self.get_account(account_code)

        if not account:
            return "Bilgi tabanında bulunmayan hesap"

        return account.get("name", "Hesap adı bulunamadı")

    def account_exists(self, account_code: str) -> bool:
        """
        Hesabın bilgi tabanında bulunup bulunmadığını kontrol eder.
        """

        return self.get_account(account_code) is not None

    def is_account_verified(self, account_code: str) -> bool:
        """
        Hesabın resmî kaynak kontrolünün tamamlanıp tamamlanmadığını döndürür.
        """

        account = self.get_account(account_code)

        if not account:
            return False

        return bool(account.get("verified", False))

    def get_accounts_by_category(self, category: str) -> list[dict]:
        """
        Belirli bir kategorideki hesapları döndürür.

        Örnek kategoriler:
        inventory
        fixed_asset
        administrative_expense
        vat_receivable
        trade_payable
        """

        normalized_category = category.strip().lower()

        return [
            account.copy()
            for account in self.accounts
            if account.get("category", "").lower()
            == normalized_category
        ]

    def get_alternative_accounts(
        self,
        account_code: str,
    ) -> list[dict]:
        """
        Bir hesap için bilgi tabanında belirtilen alternatif hesapları döndürür.
        """

        account = self.get_account(account_code)

        if not account:
            return []

        alternative_codes = account.get(
            "alternative_accounts",
            [],
        )

        alternatives = []

        for alternative_code in alternative_codes:
            alternative_account = self.get_account(
                alternative_code
            )

            if alternative_account:
                alternatives.append(alternative_account)

        return alternatives

    def get_validation_rules(self) -> list[dict]:
        """
        Muhasebe fişi doğrulama kurallarını döndürür.
        """

        return self.validation_rules.copy()

    def get_blocking_validation_rules(self) -> list[dict]:
        """
        Sağlanmadığında fiş aktarımını durduracak kuralları döndürür.
        """

        return [
            rule.copy()
            for rule in self.validation_rules
            if rule.get("blocks_export") is True
        ]

    def search_accounts(self, search_text: str) -> list[dict]:
        """
        Hesap kodu, hesap adı ve kullanım açıklamasında arama yapar.
        """

        normalized_search = search_text.strip().casefold()

        if not normalized_search:
            return []

        results = []

        for account in self.accounts:
            searchable_text = " ".join([
                str(account.get("code", "")),
                account.get("name", ""),
                account.get("usage", ""),
                account.get("category", ""),
            ]).casefold()

            if normalized_search in searchable_text:
                results.append(account.copy())

        return results