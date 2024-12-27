from hornets.components.transaction.enums import WatermarkDisplay
from framework.pos.payment.payment import Payment
from hornets.components.pos.payment.payment_method import CreditCardPaymentMethod
from hornets.models.credit_card.instances import VISA_EMV, MASTERCARD_MAGSTRIPE

@pytest.mark.pos
@pytest.mark.frontend
@pytest.mark.payment
@pytest.mark.ert
class TestPosPayItemWithCreditCard:

    @pytest.mark.parametrize("credit_card", [VISA_EMV, MASTERCARD_MAGSTRIPE])
    def test_pay_with_credit_card(self, pos, credit_card):
        pos.select_item(item="Item 7")
        transaction = pos.pay(Payment(CreditCardPaymentMethod(credit_card)))

        assert transaction["watermark"] == WatermarkDisplay.TRANSACTION_COMPLETED