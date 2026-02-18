import secrets
import string

def generate_password(length=8):
    """Generate a secure random password of specified length"""
    letters = string.ascii_letters
    digits = string.digits
    special_chars = '@$!%*?&'
    
    password = [
        secrets.choice(letters),
        secrets.choice(digits),
        secrets.choice(special_chars)
    ]
    
    all_chars = letters + digits + special_chars
    password += [secrets.choice(all_chars) for _ in range(length - 3)]
    
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)