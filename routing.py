from typing import Literal

Category = Literal["billing", "technical_support", "account_access", "other"]
Queue = Literal["billing", "technical_support", "account_access", "manual_review"]

CATEGORY_KEYWORDS: dict[Category, tuple[str, ...]] = {
    "billing": ("charged", "refund", "invoice", "payment"),
    "technical_support": ("crash", "error", "bug", "blank screen"),
    "account_access": ("password reset", "locked out", "cannot log in"),
}

CATEGORY_QUEUES: dict[Category, Queue] = {
    "billing": "billing",
    "technical_support": "technical_support",
    "account_access": "account_access",
    "other": "manual_review",
}


def classify_ticket(subject: str, message: str) -> Category:
    text = f"{subject}\n{message}".casefold()
    matches = [
        category
        for category, keywords in CATEGORY_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    ]
    return matches[0] if len(matches) == 1 else "other"


def queue_for_category(category: Category) -> Queue:
    return CATEGORY_QUEUES[category]