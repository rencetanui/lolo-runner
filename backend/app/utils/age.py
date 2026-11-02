from datetime import date 

def age_on(dob: date, on: date) -> int:
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))

def age_category(age: int, gender: str) -> str:
    prefix ={"male": "M", "female": "F", "other": "X"}[gender]
    if age < 18:
        return f"{prefix}U18"
    if age < 35:
        return f"{prefix}18-35"
    if age >=70:
        return f"{prefix}70+"
    low = (age // 5) * 5
    return f"{prefix}{low}-{low + 4}"