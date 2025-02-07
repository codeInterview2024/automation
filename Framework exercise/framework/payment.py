from typing import Union

from hornets.components.pos.payment.payment_method import (
    CreditCardPaymentMethod,
    PaymentMethod,
)

class Payment:
    def __init__(self, *payment_method: PaymentMethod):
        self.payment_method = payment_method

    def make_payment(self, pos, select_tender: bool = False):
        pos.transaction.transaction_details.payment_method = self.payment_method
        for method in self.payment_method:
            if select_tender:
                method.select_tender(pos)
            if method.is_electronic_payment_method():
                method.select_payment_type(pos)
                pos.pinpad.wait_for_pinpad_to_be_ready()
            method.pay_with(pos)

    def make_outside_payment(self, crind):
        crind.transaction.transaction_details.payment_method = self.payment_method
        self.payment_method[0].pay_outside_with(crind)

    def select_tender(self, pos):
        self.payment_method[0].select_tender(pos)

    def has_electronic_payment(self):
        return any(method.is_electronic_payment_method() for method in self.payment_method)

class NoPayment(Payment):

    def __init__(self):
        super().__init__()
        self.payment_method = []

    def has_electronic_payment(self):
        return False
