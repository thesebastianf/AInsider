"""
AInsider Tracker – Name Normalization Utility
"""

def normalize_person_name(name: str) -> str:
    """Normalize names from 'Lastname, Firstname' to 'Firstname Lastname'.
    Skips corporate names and funds using typical suffixes.
    Handles standard suffixes like Jr., Sr., III, etc.
    """
    if not name:
        return name
    name = name.strip()
    if "," in name:
        parts = [p.strip() for p in name.split(",")]
        # Corporate suffixes to skip reversing
        corporate_suffixes = {"LP", "LLC", "INC", "CORP", "AG", "SE", "GMBH", "LTD", "PARTNERS", "ASSOCIATES"}
        if any(p.upper().replace(".", "") in corporate_suffixes for p in parts):
            return name
        
        if len(parts) == 2:
            last, first = parts
            return f"{first} {last}"
        elif len(parts) == 3:
            last, first, suffix = parts
            if suffix.lower() in ["jr.", "jr", "sr.", "sr", "ii", "iii", "iv"]:
                return f"{first} {last}, {suffix}"
            return f"{first} {last} {suffix}"
    return name
