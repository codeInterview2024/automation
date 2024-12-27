import re
from typing import Union

from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.common import TimeoutException as SeleniumTimeoutException

from hornets.base import Base
from hornets.components.exceptions import (
    NotApplicableDiscountException,
    ElementNotFoundException,
    NgfcExceedLimitsException,
    SplitTenderNotAllowedException,
    TransactionCancelledException,
    CardNotSupportedException,
    AbortTransactionException,
    UnexpectedDispenserDetailException,
    UnexpectedPosPromptException,
    TransactionNotVoidableException,
    NoBufferAvailableException,
)
from hornets.components.keypad.keyboard_keypad import PosKeyboardKeypad
from hornets.components.keypad.number_keypad import PosNumberKeyPad
from hornets.components.pinpad import Pinpad
from hornets.components.pos.constants import PINPAD_ERROR_IN_POS
from hornets.components.pos.enums import (
    PayMode,
    PosStateName,
    ItemChangeQuantityMethod,
    ItemSelectionMethod,
    DiscountType,
    SafeDropStatus,
    PaymentMethodName,
)
from hornets.components.pos.payment.payment_method import (
    CheckPaymentMethod,
    PaperCheckPaymentMethod,
)
from hornets.components.pos.payment.payment import Payment, NoPayment
from hornets.components.pos.receipts.receipt import Receipt
from hornets.components.pos.receipts.receipts_searcher import IndoorReceiptSearcher
from hornets.components.pos.pos_locators import (
    PosMainLocators,
    FunctionKeysLocators,
    PosPromptBoxLocators,
    NumberKeypadLocators,
    HeaderLocators,
    SelectionListLocators,
    JournalDisplayLocators,
)
from hornets.components.transaction.transaction import PosTransaction

class Pos(Base):
    def __init__(self, driver: WebDriver, active_tabs, ip_scanner=None):
        super().__init__(driver, active_tabs)
        self.printer_installed = False
        self.number_keypad = PosNumberKeyPad(self.driver)
        self.keyboard = PosKeyboardKeypad(self.driver)
        self.transaction = PosTransaction(self.driver)
        self.prompt_box = PromptBox(self.driver)
        self.header = Header(self.driver)
        self.pinpad = Pinpad(self.driver, self, pinpad_locator=PosMainLocators.PINPAD_PROCESSING_TEXT)
        self.scanner = ip_scanner or IpScanner()
        self.pay_mode = PayMode.DEFAULT
        self.pos_state = UnknownPosState()

    @staticmethod
    def _get_payment(payment: Payment, pay_mode: PayMode) -> Payment | NoPayment:
        """
        Get the proper Payment to advance with pay process.
        Args:
            payment (Payment): Payment to return if not None and transaction is not zero amount
            pay_mode (PayMode): PayMode to check zero amount transactions special case
        Return:
            (Payment | NoPayment): Payment or NoPayment to return
        """
        if pay_mode == PayMode.ZERO_AMOUNT_TRANSACTION:
            return NoPayment()
        return payment

    def select_item(
            self,
            item: str = "Item 1",
            from_group: str = None,
            page: int = 1,
            selection_method: ItemSelectionMethod = ItemSelectionMethod.SPEED_KEY,
            price: str = None,
            quantity: str = None,
            carwash: CarWash = None,
            restricted_item_config: RestrictedItemConfig = None,
            qualifier_item_config: QualifierItemConfig = None
    ):
        """
        This will select item as per selection method
        Args:
            item: (str) Name of item to be added.
            from_group: (str) Name of group from which item is to be selected.
            page (int): Page number of item to be selected.
            selection_method: (BaseEnum) This can be either PLU or SPEED KEYS or DEPT KEYS from ItemSelectionMethod
            price: (str) Price of item. Mandatory for DEPT KEY method and for item having price required enabled
            quantity: (str) Quantity of item. This is mandatory for item having quantity required enabled
            carwash: (CarWash object) Configuration for selecting Carwash item with package
            restricted_item_config: (class object) Configuration for restricted Item
            qualifier_item_config: (class object) Configuration for qualifier Item
        """
        self.transaction.transaction_details.is_drystock = True
        match selection_method:
            case ItemSelectionMethod.SPEED_KEY:
                self.select_item_page(page)
                self.select_group(from_group)
                self.select_item_by_speedkey(item)
            case ItemSelectionMethod.PLU:
                self.select_item_by_plu(item)
            case ItemSelectionMethod.DEPT_KEY:
                self.select_item_by_deptkey(item)
            case _:
                raise UnexpectedItemSelectionMethod(
                    f"Received {selection_method} for selection. \n"
                    f"selection method must be <PLU|DEPT KEY|SPEED KEY>"
                )
        try:
            if price is not None:
                self.number_keypad.enter_price(price)
            if quantity is not None:
                self.number_keypad.enter_value(quantity)
        except ElementNotFoundException:
            raise ValueError("Please provide correct value to enter")

        self._set_pos_state(PosStateName.IN_TRANSACTION)

    def _process_pay_mode(self, payment: Payment, pay_mode: PayMode, loyalty: Loyalty, donation: Donation):
        """
        Process the payment mode
        """
        if pay_mode:
            self._set_pay_mode(pay_mode)
        logger.info(f"POS Pay - Selected PayMode: {self.pay_mode}")
        match self.pay_mode:
            case PayMode.DEFAULT:
                self.click(FunctionKeysLocators.PAY)
                donation.process(self)
                loyalty.process_indoor(self)
                self._set_pos_state(PosStateName.IN_TRANSACTION_SELECTING_TENDER)
                payment.make_payment(self, select_tender=True)
            case PayMode.ONLY_CARDS:
                loyalty.process_indoor(self)
                self._set_pos_state(PosStateName.IN_TRANSACTION_AFTER_PAYMENT)
                if not payment.has_electronic_payment():
                    raise PaymentNotPerformedException("Only electronic payments are supported")
                payment.make_payment(self)
    
    def pay(
            self,
            payment: Payment = None,
            loyalty: Loyalty = NoLoyalty(),
            pay_mode: PayMode = None,
            gift_card: GiftCard = NoGiftCard(),
            donation: Donation = NoDonation(),
            expected_error: bool = False
    ) -> dict:
        """
        Pay the transaction with the given payment method
        Args:
            payment (Payment): Payment method to use
            loyalty (Loyalty): Loyalty card to use
            pay_mode (PayMode): Pay mode to use
            gift_card (GiftCard): Gift card to use
            donation (Donation): Donation to use
            expected_error (bool): If an error is expected
        Return:
            dict: Transaction completed
        """
        payment = self._get_payment(payment, pay_mode)
        self._process_pay_mode(payment, pay_mode, loyalty, donation)
        self._check_for_additional_prompts(payment, expected_error)
        gift_card.activation_or_recharge_process(self)
        self._post_payment_actions(payment)
        return self.transaction.to_dict(after_payment=True)

    def _post_payment_actions(self, payment: Payment):
        """
        Confirm the transaction has been completed
        """
        if payment.has_electronic_payment():
            self.pinpad.wait_for_pinpad_transaction_completion()
        self.transaction.wait_for_transaction_to_be_completed()

    
