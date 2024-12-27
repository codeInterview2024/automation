from abc import ABC, abstractmethod
from typing import List
from typing import Union

from hornets.base_enum import BaseEnum
from hornets.components.pos.config.refund_config import RefundConfig
from hornets.components.pos.enums import PaymentMethodName, PosStateName
from hornets.utilities.log_config import logger
from libs.simulators_interface.pinpadsim.enums import PinpadMessage
from hornets.utilities.iterables import get_iterable
from hornets.components.el.el_locators import ReceiptJournalLocators


class PaymentMethod(ABC):
    def __init__(self, payment_method: PaymentMethodName, tender_button: BaseEnum, needs_pinpad: bool = False):
        self.payment_method_name = payment_method
        self.tender_button = tender_button
        self.needs_pinpad = needs_pinpad

    def __str__(self):
        return f"{self.payment_method_name}"

    @abstractmethod
    def pay_with(self, pos):
        raise NotImplementedError

    def select_payment_type(self, pos):
        pass

    def pay_express_lane_with(self, el, loyalty):
        raise NotImplementedError

    def refund_with(self, pos):
        raise NotImplementedError

    def is_electronic_payment_method(self):
        return self.needs_pinpad

    def select_tender(self, pos):
        logger.info(f"Selecting tender: {self.payment_method_name}")
        pos._select_tender(self.tender_button)

    def pay_outside_with(self, pos):
        raise NotImplementedError

class CreditCardPaymentMethod(PaymentMethod):
    def __init__(
            self,
            credit_card: Card = VISA_MAGSTRIPE,
            credit_card_limit: str = None,
            offline_limit: float = None,
            refund_config: RefundConfig = None,
            manual_entry: bool = False
    ):
        super().__init__(
            payment_method=PaymentMethodName.CREDIT_CARD,
            tender_button=FunctionKeysLocators.CARD,
            needs_pinpad=True
        )
        self.credit_card = credit_card
        self.credit_card_limit = credit_card_limit
        self.offline_limit = offline_limit
        self.refund_config = refund_config
        self.manual_entry = manual_entry

    def pay_with(self, pos):
        pos.pinpad.wait_for_pinpad_card_action()
        self.process_indoor_payment(pos, self.manual_entry)
        if self.credit_card_limit:
            self.process_credit_card_limit(pos)
        if self.offline_limit:
            self.process_offline_credit_card_limit(pos)

    def pay_outside_with(self, crind):
        crind._process_outside_payment_with_card(self.credit_card)

    def process_indoor_payment(self, pos, manual_entry):
        pos._set_pos_state(PosStateName.IN_TRANSACTION_AFTER_PAYMENT)
        if manual_entry:
            self.credit_card.process_manual_payment(pos)
        else:
            self.credit_card.process_payment(pos)

    def process_credit_card_limit(self, pos):
        if float(self.credit_card_limit) < float(pos.get_transaction_total_amount()):
            logger.info(f"Processing transaction with credit card limit for ${self.credit_card_limit}")
            pos.prompt_box.wait_for_pos_prompt(
                PosPrompt.PARTIAL_APPROVAL,
                additional_attribute=f"{float(self.credit_card_limit):.2f}"
            )
            pos.answer_to_prompt(PosPrompt.PARTIAL_APPROVAL, PosPromptBoxLocators.YES)
        else:
            logger.info(f"The credit card limit ({self.credit_card_limit}) exceeds the total transaction amount"
                        f" ({pos.get_transaction_total_amount()})."
                        f" Proceeding with the transaction.")


class DebitCardPaymentMethod(PaymentMethod):
    def __init__(self, debit_card: Card = GENERIC_DEBIT_MAGSTRIPE, cashback_amount: str = None):
        super().__init__(
            payment_method=PaymentMethodName.DEBIT_CARD,
            tender_button=FunctionKeysLocators.CARD,
            needs_pinpad=True
        )
        self.debit_card = debit_card
        self.cashback_amount = cashback_amount

    def pay_with(self, pos):
        pos.pinpad.wait_for_pinpad_card_action()
        pos._set_pos_state(PosStateName.IN_TRANSACTION_AFTER_PAYMENT)
        self.debit_card.process_payment(pos, cashback_amount=self.cashback_amount)
        pos.transaction.transaction_details.cashback = True if self.cashback_amount else False

    def pay_outside_with(self, crind):
        crind._process_outside_payment_with_card(self.debit_card)