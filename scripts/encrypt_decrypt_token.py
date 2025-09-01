#!/usr/bin/env python3
"""
Token Encryption/Decryption Utility
Encrypts or decrypts tokens using the system's encryption method
"""

import os
import sys
import argparse

def setup_path():
    """Add the backend service to the path for imports"""
    backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'services', 'backend-service')
    if backend_path not in sys.path:
        sys.path.append(backend_path)

def encrypt_token(token):
    """Encrypt a token using the system's encryption method"""
    try:
        setup_path()
        from app.core.config import AppConfig
        
        print(f"🔐 Encrypting token: {token[:10]}...{token[-4:] if len(token) > 14 else 'SHORT'}")
        
        # Load the encryption key
        key = AppConfig.load_key()
        print("✅ Encryption key loaded successfully")
        
        # Encrypt the token
        encrypted_token = AppConfig.encrypt_token(token, key)
        print("✅ Token encrypted successfully")
        
        return encrypted_token
        
    except Exception as e:
        print(f"❌ Encryption failed: {e}")
        return None

def decrypt_token(encrypted_token):
    """Decrypt a token using the system's encryption method"""
    try:
        setup_path()
        from app.core.config import AppConfig
        
        print(f"🔓 Decrypting token: {encrypted_token[:20]}...{encrypted_token[-10:] if len(encrypted_token) > 30 else 'SHORT'}")
        
        # Load the encryption key
        key = AppConfig.load_key()
        print("✅ Encryption key loaded successfully")
        
        # Decrypt the token
        decrypted_token = AppConfig.decrypt_token(encrypted_token, key)
        print("✅ Token decrypted successfully")
        
        return decrypted_token
        
    except Exception as e:
        print(f"❌ Decryption failed: {e}")
        return None

def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(
        description="Encrypt or decrypt tokens using the system's encryption method",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Encrypt a GitHub token
  python scripts/encrypt_decrypt_token.py encrypt ghp_1234567890abcdef

  # Decrypt an encrypted token
  python scripts/encrypt_decrypt_token.py decrypt gAAAAABh...

  # Interactive mode (prompts for token)
  python scripts/encrypt_decrypt_token.py encrypt
  python scripts/encrypt_decrypt_token.py decrypt
        """
    )
    
    parser.add_argument(
        'action',
        choices=['encrypt', 'decrypt'],
        help='Action to perform: encrypt or decrypt'
    )
    
    parser.add_argument(
        'token',
        nargs='?',
        help='Token to encrypt/decrypt (if not provided, will prompt)'
    )
    
    parser.add_argument(
        '--output-sql',
        action='store_true',
        help='Output SQL UPDATE statement for database (encrypt mode only)'
    )
    
    parser.add_argument(
        '--integration-name',
        default='GITHUB',
        help='Integration name for SQL output (default: GITHUB)'
    )
    
    args = parser.parse_args()
    
    print("🔧 Token Encryption/Decryption Utility")
    print("=" * 50)
    
    # Get token from argument or prompt
    if args.token:
        token = args.token
    else:
        if args.action == 'encrypt':
            token = input("Enter token to encrypt: ").strip()
        else:
            token = input("Enter encrypted token to decrypt: ").strip()
    
    if not token:
        print("❌ No token provided")
        return 1
    
    # Perform the requested action
    if args.action == 'encrypt':
        result = encrypt_token(token)
        
        if result:
            print("\n" + "=" * 50)
            print("📋 Encryption Results:")
            print(f"   Original Token: {token[:10]}...{token[-4:] if len(token) > 14 else 'SHORT'}")
            print(f"   Encrypted Token: {result}")
            
            if args.output_sql:
                print(f"\n💡 SQL UPDATE statement for {args.integration_name} integration:")
                print(f"   UPDATE integrations SET password = '{result}' WHERE name = '{args.integration_name}';")
            else:
                print(f"\n💡 To update database, run with --output-sql flag")
        else:
            print("\n❌ Failed to encrypt token")
            return 1
            
    elif args.action == 'decrypt':
        result = decrypt_token(token)
        
        if result:
            print("\n" + "=" * 50)
            print("📋 Decryption Results:")
            print(f"   Encrypted Token: {token[:20]}...{token[-10:] if len(token) > 30 else 'SHORT'}")
            print(f"   Decrypted Token: {result}")
            print(f"\n⚠️  Keep the decrypted token secure!")
        else:
            print("\n❌ Failed to decrypt token")
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
