from decimal import Decimal, ROUND_HALF_UP


class TaxEngine:
    """
    MarkaAI Vergi Motoru

    Bu motor;

    - Standart KDV
    - Tevkifat
    - İhraç kayıtlı teslim
    - İstisna
    - Stopaj
    - Bordro vergileri
    - Beyanname hesaplamaları

    için ortak hesaplama motorudur.
    """

    def __init__(self):
        pass

    # --------------------------------------------------

    def calculate_standard_vat(
        self,
        subtotal,
        vat_rate,
    ):
        """
        Standart KDV hesaplar.
        """

        subtotal = self._decimal(subtotal)
        vat_rate = self._decimal(vat_rate)

        vat = (
            subtotal
            * vat_rate
            / Decimal("100")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        total = subtotal + vat

        return {
            "subtotal": subtotal,
            "vat_rate": vat_rate,
            "vat_amount": vat,
            "total": total,
        }

    # --------------------------------------------------

    def calculate_withholding(
        self,
        subtotal,
        vat_rate,
        numerator,
        denominator,
    ):
        """
        Kısmi tevkifat hesaplar.
        """

        standard = self.calculate_standard_vat(
            subtotal,
            vat_rate,
        )

        gross_vat = standard["vat_amount"]

        withheld = (
            gross_vat
            * self._decimal(numerator)
            / self._decimal(denominator)
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        seller_vat = gross_vat - withheld

        payable = (
            standard["subtotal"]
            + seller_vat
        )

        return {
            "subtotal": standard["subtotal"],
            "vat_rate": standard["vat_rate"],
            "gross_vat": gross_vat,
            "withheld_vat": withheld,
            "seller_vat": seller_vat,
            "supplier_payable": payable,
        }

    # --------------------------------------------------

    def calculate_export_registered(
        self,
        subtotal,
        vat_rate,
    ):
        """
        İhraç kayıtlı teslim.
        """

        standard = self.calculate_standard_vat(
            subtotal,
            vat_rate,
        )

        return {
            "subtotal": standard["subtotal"],
            "vat_rate": standard["vat_rate"],
            "calculated_vat": standard["vat_amount"],
            "collected_vat": Decimal("0.00"),
            "deferred_vat": standard["vat_amount"],
            "invoice_total": standard["subtotal"],
        }

    # --------------------------------------------------

    def _decimal(self, value):

        if isinstance(value, Decimal):
            return value

        value = (
            str(value)
            .replace("TL", "")
            .replace("₺", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )

        return Decimal(value)