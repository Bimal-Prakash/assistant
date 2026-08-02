import re

class PrivacyFilter:
    def __init__(self):
        # Basic patterns for sensitive data
        self.patterns = [
            (re.compile(r'(?i)(?:sk-[a-zA-Z0-9]{32,}|sk_live_[a-zA-Z0-9]{20,}|eyJ[a-zA-Z0-9-_]+\.[a-zA-Z0-9-_]+\.[a-zA-Z0-9-_]+)'), "[REDACTED_TOKEN]"), # API Keys / JWTs
            (re.compile(r'\b(?:\d[ -]*?){13,16}\b'), "[REDACTED_CC]"), # Credit Cards
            (re.compile(r'(?i)(password|passwd|pwd)\s*[:=]\s*\S+'), r'\1: [REDACTED_PASSWORD]'), # Passwords
            (re.compile(r'\b(?:\+\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b'), "[REDACTED_PHONE]"), # Phone numbers
        ]

    def scrub(self, text: str) -> str:
        if not text:
            return text
        for pattern, replacement in self.patterns:
            text = pattern.sub(replacement, text)
        return text

privacy_filter = PrivacyFilter()
