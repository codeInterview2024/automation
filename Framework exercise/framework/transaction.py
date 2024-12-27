import re
from typing import Union, List

from selenium.webdriver.chrome.webdriver import WebDriver

from hornets.base_enum import BaseEnum
from hornets.components.el.el_locators import ReceiptJournalLocators
from hornets.components.exceptions import ReceiptNotFoundException
from hornets.components.transaction.enums import WatermarkDisplay, ScreenMessageDisplay
from hornets.components.pos.pos_locators import JournalDisplayLocators
from hornets.base import Base
from hornets.components.transaction.screen_message import ScreenMessage
from hornets.components.transaction.transaction_details import TransactionDetails
from hornets.components.transaction.watermark import Watermark
from hornets.tools.receipt.tool import ReceiptTool
from hornets.utilities.constants import POLLING_TIMEOUT, POLLING_STEP
from hornets.utilities.log_config import logger
from hornets.utilities.polling_wrapper import poll_until_true

class Transaction(Base):

    def __init__(self, driver: WebDriver, transaction_locators):
        super().__init__(driver)
        self.transaction_locators = transaction_locators

    def _get_transaction_items(self):
        transaction_details = []
        details = self.find_elements(self.transaction_locators.TRANSACTION_DETAILS_DESCRIPTION)
        for index, detail in enumerate(details, 1):
            transaction_details.append(
                {
                    "name": self.get_text(self.transaction_locators.ITEM_DESCRIPTION, additional_attribute=str(index)),
                    "price": self.get_text(self.transaction_locators.ITEM_PRICE, additional_attribute=str(index)),
                }
            )
        return transaction_details

class PosTransaction(Transaction):

    def __init__(self, driver: WebDriver):
        super().__init__(driver, transaction_locators=JournalDisplayLocators)
        self.transaction_details = TransactionDetails()
        self.watermark = Watermark(self.driver)
        self.receipt = None
        self.last_receipt_number = ReceiptTool().get_last_indoor_receipt_number()
        self.complete_fueling_after_payment = False
        self.fuel_selection_to_dispense = None

    def to_dict(self, after_payment: bool = False) -> dict:
        """
        Return the transaction display as a dict
        Return:
            dict: Transaction display as a dict
        """

        return {
            "journal_display": {
                "items": self._get_transaction_items(),
                "total_amount": self._get_transaction_total_amount(),
                "discounts": {
                    "transaction_discounts": self._get_transaction_discounts(),
                    "item_discounts": self._get_items_discounts(),
                },
                "loyalties": self.get_loyalties(),
            },
            "watermark": self.watermark.status,
            "receipt": self.get_last_register_receipt() if after_payment else self.receipt,
            **self.transaction_details.to_dict(),
        }

    def _get_transaction_total_amount(self) -> dict:
        """
        Get the values from the total transaction
        Return:
            dict: Total transaction values
        """
        return {
            "total": self.find_element(JournalDisplayLocators.TOTAL_AMOUNT).text.replace("$", ""),
            "basket_count": int(self.find_element(JournalDisplayLocators.BASKET_COUNT).text),
        }

    def wait_for_transaction_to_be_completed(self):
        """
        Wait for the transaction to be completed
        Return:
            bool: True if the transaction is completed, False otherwise
        """
        return self.watermark.wait_for_transaction_to_be_in_status(WatermarkDisplay.TRANSACTION_COMPLETED)


    def _get_transaction_discounts(self) -> List:
        """
        Get the  transaction discounts
        Return:
            list: Contains transactions discounts
        """
        if not self.element_exists(JournalDisplayLocators.TRANSACTION_DISCOUNTS):
            return []
        transaction_discounts = []
        transaction_discount_elements = self.find_elements(JournalDisplayLocators.TRANSACTION_DISCOUNTS)
        for index, element in enumerate(transaction_discount_elements, 1):
            description = self.get_text(
                JournalDisplayLocators.TRANSACTION_DISCOUNT_DESCRIPTION, additional_attribute=str(index)
            )
            price = self.get_text(JournalDisplayLocators.TRANSACTION_DISCOUNT_AMOUNT, additional_attribute=str(index))
            transaction_discounts.append({"description": description, "price": price})
        return transaction_discounts