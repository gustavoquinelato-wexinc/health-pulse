#!/usr/bin/env python3
"""
Script to generate secure secret keys for the ETL service.
Run this script to generate new SECRET_KEY and ENCRYPTION_KEY values.
"""

import secrets
import base64
from cryptography.fernet import Fernet

def generate_secret_key(length: int = 32) -> str:
    """Generate a secure random secret key."""
    return secrets.token_urlsafe(length)

def generate_encryption_key() -> str:
    """Generate a Fernet-compatible encryption key."""
    return Fernet.generate_key().decode()

def main():
    print("🔐 Generating secure keys for ETL Service...")
    print()
    
    # Generate JWT_SECRET_KEY
    jwt_secret_key = generate_secret_key()
    print(f"JWT_SECRET_KEY=\"{jwt_secret_key}\"")

    # Generate SECRET_KEY
    secret_key = generate_secret_key()
    print(f"SECRET_KEY=\"{secret_key}\"")

    # Generate ENCRYPTION_KEY
    encryption_key = generate_encryption_key()
    print(f"ENCRYPTION_KEY=\"{encryption_key}\"")
    
    print()
    print("✅ Keys generated successfully!")
    print()
    print("📝 Instructions:")
    print("1. Copy the keys above")
    print("2. Update your .env file with these new values")
    print("3. Keep these keys secure and never commit them to version control")
    print("4. Use different keys for different environments (dev, staging, prod)")
    print()
    print("⚠️  Important: Save these keys securely. If you lose them, you won't be able to decrypt existing data!")

if __name__ == "__main__":
    main()
