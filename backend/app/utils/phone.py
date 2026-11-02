import re


def normalize_phone(value: str) -> str:
    s = re.sub(r"[\s\-()]", "", value)
    if re.fullmatch(r"0[17]\d{8}", s):          # 0712345678
        return "+254" + s[1:]
    if re.fullmatch(r"254[17]\d{8}", s):        # 254712345678
        return "+" + s
    if re.fullmatch(r"\+254[17]\d{8}", s):      # +254712345678
        return s
    if re.fullmatch(r"\+[1-9]\d{7,14}", s):     # other international numbers
        return s
    raise ValueError("Enter a valid phone number, e.g. 0712 345 678")