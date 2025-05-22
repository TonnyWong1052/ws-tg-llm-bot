#!/usr/bin/env python3
"""
This script handles initial Telegram session setup for non-interactive environments.
Run this interactively once to create the session file, then deploy to your server.
"""

import os
import sys
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from dotenv import load_dotenv

# Add the parent directory to the Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ensure config directory exists
config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config')
os.makedirs(config_dir, exist_ok=True)

# Load environment variables from config/.env
config_env_path = os.path.join(config_dir, '.env')
if os.path.exists(config_env_path):
    load_dotenv(config_env_path)
    print(f"Loaded environment variables from {config_env_path}")
else:
    print(f"Not found {config_env_path}, trying to load from root directory")
    root_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(root_env_path):
        load_dotenv(root_env_path)
        print(f"Loaded environment variables from {root_env_path}")
        # Move .env to config directory
        os.rename(root_env_path, config_env_path)
        print(f"Moved .env to {config_env_path}")
    else:
        print("No .env file found. Please create a .env file with required environment variables")
        sys.exit(1)

# Get Telegram API credentials from environment variables
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')

# Validate required environment variables
if not API_ID or not API_HASH or not PHONE_NUMBER:
    print("Missing required environment variables. Please ensure .env file contains API_ID, API_HASH and PHONE_NUMBER")
    sys.exit(1)

try:
    API_ID = int(API_ID)
except ValueError:
    print("API_ID must be an integer")
    sys.exit(1)

SESSION_NAME = 'session_name'
SESSION_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'session_name.session')

async def create_session():
    """Create a Telegram session"""
    print(f"Creating Telegram session for {PHONE_NUMBER}")
    
    # Check if session file already exists
    if os.path.exists(SESSION_PATH):
        print(f"Session file already exists at {SESSION_PATH}")
        choice = input("Do you want to recreate the session? (y/N): ").strip().lower()
        if choice != 'y':
            print("Keeping existing session. No changes made.")
            return

    # Create a new session
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    try:
        print("Starting client and requesting login code...")
        await client.connect()
        
        if not await client.is_user_authorized():
            print(f"Not authorized. Sending code request to {PHONE_NUMBER}...")
            await client.send_code_request(PHONE_NUMBER)
            code = input("Enter the code you received: ")
            
            try:
                await client.sign_in(PHONE_NUMBER, code)
                print("Successfully signed in!")
            except SessionPasswordNeededError:
                password = input("Enter your two-factor authentication password: ")
                await client.sign_in(password=password)
                print("Successfully signed in with 2FA!")
            except PhoneCodeInvalidError:
                print("Invalid verification code")
                sys.exit(1)
            except Exception as e:
                print(f"Error during sign in: {e}")
                sys.exit(1)
        else:
            print("Already authorized! Session is valid.")
        
        # Save session
        print(f"Session saved to {SESSION_PATH}")
        print("\nYou can now deploy this session file to your server.")
        print("The bot should start without asking for a code.")
        
    except Exception as e:
        print(f"Error creating session: {e}")
        sys.exit(1)
    finally:
        await client.disconnect()

async def verify_session():
    """Verify if the session file exists and is valid"""
    if not os.path.exists(SESSION_PATH):
        print(f"Session file does not exist at {SESSION_PATH}")
        print("Please run this script interactively first to create a session.")
        return False
    
    print(f"Session file exists at {SESSION_PATH}")
    
    # Try to connect to verify the session
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    try:
        await client.connect()
        if await client.is_user_authorized():
            print("Session verification successful")
            return True
        else:
            print("Session is invalid or expired")
            return False
    except Exception as e:
        print(f"Error verifying session: {e}")
        return False
    finally:
        await client.disconnect()

def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--verify':
        # Just verify session exists
        if asyncio.run(verify_session()):
            print("Session verification: OK")
            sys.exit(0)
        else:
            print("Session verification: FAILED")
            sys.exit(1)
    else:
        # Create session interactively
        asyncio.run(create_session())

if __name__ == "__main__":
    main()