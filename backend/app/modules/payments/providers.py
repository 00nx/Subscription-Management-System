"""Payment providers. The gateway is a plug-in: add a Razorpay/Stripe class with the same two methods and register it.

The frontend never decides whether a payment succeeded. For the simulated provider it only *chooses a test outcome*
(like picking a test card); this module validates that choice and the service layer records the result.
"""
import secrets
from dataclasses import dataclass


@dataclass
class ProviderResult:
    status: str  # PENDING | SUCCESS | FAILED | CANCELLED
    reference: str
    message: str = ""


class SimulatedProvider:
    name = "SIMULATED"
    OUTCOMES = {"SUCCESS", "FAILED", "CANCELLED"}

    def initiate(self, payment) -> ProviderResult:
        return ProviderResult("PENDING", f"SIM-{secrets.token_hex(8).upper()}", "Awaiting simulated gateway confirmation")

    def complete(self, payment, outcome: str) -> ProviderResult:
        if outcome not in self.OUTCOMES:
            raise ValueError("Unknown outcome")
        msgs = {"SUCCESS": "Simulated payment approved", "FAILED": "Simulated payment declined", "CANCELLED": "Payment cancelled by the payer"}
        return ProviderResult(outcome, payment.transaction_reference or "", msgs[outcome])


PROVIDERS = {SimulatedProvider.name: SimulatedProvider()}


def get_provider(name: str):
    return PROVIDERS[name]
