"""Dev only: act as Safaricom and answer the latest pending payment.

  python -m scripts.simulate_stk_callback            # customer paid
  python -m scripts.simulate_stk_callback --code 1032   # customer cancelled
"""
import argparse

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.modules.auth import models as _auth  # noqa: F401
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.registrations import models as _reg  # noqa: F401

parser = argparse.ArgumentParser()
parser.add_argument("--code", type=int, default=0, help="0 = paid, 1032 = cancelled, 1 = insufficient funds")
parser.add_argument("--base-url", default="http://127.0.0.1:8000")
parser.add_argument("--amount", type=float, default=None, help="pretend a different amount was paid")
args = parser.parse_args()

with SessionLocal() as db:
    payment = db.scalars(
        select(Payment)
        .where(Payment.status == PaymentStatus.pending, Payment.checkout_request_id.is_not(None))
        .order_by(Payment.created_at.desc())
    ).first()
    if not payment:
        raise SystemExit("No pending payment found")
    checkout_id, amount, phone = payment.checkout_request_id, payment.amount, payment.phone

stk = {
    "MerchantRequestID": "simulated",
    "CheckoutRequestID": checkout_id,
    "ResultCode": args.code,
    "ResultDesc": "The service request is processed successfully." if args.code == 0 else "Simulated failure",
}
if args.code == 0:
    stk["CallbackMetadata"] = {"Item": [
        {"Name": "Amount", "Value": args.amount if args.amount is not None else float(amount)},
        {"Name": "MpesaReceiptNumber", "Value": "SIM" + checkout_id[-7:].upper()},
        {"Name": "TransactionDate", "Value": 20261102120000},
        {"Name": "PhoneNumber", "Value": int(phone.lstrip("+"))},
    ]}

url = f"{args.base_url}/api/v1/payments/callbacks/stk/{settings.mpesa_callback_secret}"
res = httpx.post(url, json={"Body": {"stkCallback": stk}}, timeout=10)
print(res.status_code, res.text)