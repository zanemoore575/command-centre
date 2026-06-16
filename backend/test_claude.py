#!/usr/bin/env python3
"""
Quick test script to verify Claude API is working
"""
import os
from anthropic import Anthropic

# Load API key from .env
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")

print("=" * 60)
print("Testing Claude API Connection")
print("=" * 60)
print(f"\nAPI Key loaded: {api_key[:20]}..." if api_key else "ERROR: No API key found!")

if not api_key:
    print("\nERROR: ANTHROPIC_API_KEY not found in .env file")
    exit(1)

# Initialize client
try:
    print("\nInitializing Anthropic client...")
    client = Anthropic(api_key=api_key)
    print("✓ Client initialized successfully")
except Exception as e:
    print(f"✗ Error initializing client: {e}")
    exit(1)

# Test API call
print("\nTesting API call with model: claude-sonnet-4-5-20250929")
print("Sending simple test message...\n")

try:
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": "Say 'Hello, the API is working!' and nothing else."}
        ]
    )

    response_text = message.content[0].text
    print("=" * 60)
    print("SUCCESS! Claude API Response:")
    print("=" * 60)
    print(response_text)
    print("\n✓ Claude API is working correctly!")

except Exception as e:
    print("=" * 60)
    print("ERROR calling Claude API:")
    print("=" * 60)
    print(f"Error type: {type(e).__name__}")
    print(f"Error message: {e}")
    print("\n✗ Claude API call failed")

    # Check if it's a 404 error
    if "404" in str(e):
        print("\nThis is a 404 error - the model name is not recognized.")
        print("The model 'claude-sonnet-4-5-20250929' may not be available for your API key.")
        print("\nTrying with claude-3-5-sonnet-20241022 instead...")

        try:
            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": "Say 'Hello, the API is working!' and nothing else."}
                ]
            )
            response_text = message.content[0].text
            print(f"\n✓ SUCCESS with claude-3-5-sonnet-20241022!")
            print(f"Response: {response_text}")
            print("\nRECOMMENDATION: Update claude_client.py to use 'claude-3-5-sonnet-20241022'")
        except Exception as e2:
            print(f"✗ Also failed with claude-3-5-sonnet-20241022: {e2}")

    exit(1)

print("\n" + "=" * 60)
print("All tests passed! Your Claude API setup is working.")
print("=" * 60)
