from hornets.utilities.iterables import get_iterable

class TransactionDetails:

    def __init__(self, indoor_transaction: bool = True):
        self.indoor_transaction = indoor_transaction
        self.cash_advance_requested = False
        self.cash_advance_amount = None
        self.additional_products = None
        self.fuel_transaction = None
        self.is_ngfc = False
        self.is_fill_up = False
        self.loyalty = False
        self.payment_method = None
        self.cashback = False
        self.safe_drop = None
        self.payment_method = None
        self.car_wash = None
        self.is_drystock = False

    def to_dict(self):
        if isinstance(self.payment_method, tuple) and len(self.payment_method) == 1:
            self.payment_method = self.payment_method[0]
        return {
            "fuel_transaction": self.fuel_transaction,
            "ngfc_details": {
                "is_ngfc": self.is_ngfc,
                "is_fill_up": self.is_fill_up,
                "additional_products": self.additional_products,
            },
            "cash_advance_requested": self.cash_advance_requested,
            "cash_advance_amount": self.cash_advance_amount,
            "loyalty": self.loyalty,
            "payment_method": self.payment_method,
            "cashback": self.cashback,
        }
