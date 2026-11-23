from ai_classifier import classify_ticket_with_ai
from routing import classify_ticket

cases = [
    ("I was charged twice for my subscription.", "billing"),
    ("Can you send me last month's invoice?", "billing"),
    ("My card was debited but the order was cancelled.", "billing"),
    ("The app crashes when I open settings.", "technical_support"),
    ("The dashboard shows a blank screen.", "technical_support"),
    ("Pressing Export does nothing.", "technical_support"),
    ("I need a password reset.", "account_access"),
    ("I can't sign in to my account.", "account_access"),
    ("My verification code never arrives.", "account_access"),
    ("I need help.", "other"),
    ("I need a refund and a password reset.", "other"),
    ("Where can I read about your company?", "other"),
]

rules_correct = 0
groq_correct = 0

for message, expected in cases:
    rules = classify_ticket("Support request", message)
    groq = classify_ticket_with_ai("Support request", message)

    rules_correct += rules == expected
    groq_correct += groq == expected

    print(message)
    print(f"  Expected: {expected} | Rules: {rules} | Groq: {groq}")

total = len(cases)
print(f"\nKeyword accuracy: {rules_correct}/{total} ({rules_correct / total:.1%})")
print(f"Groq accuracy:    {groq_correct}/{total} ({groq_correct / total:.1%})")