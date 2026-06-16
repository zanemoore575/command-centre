import json
import requests
import time

# --- CONFIGURATION ---
FILE_PATH = 'conversations.json'
N8N_WEBHOOK_URL = 'https://n8n-service-8act.onrender.com/webhook/ingest-conversation' 
START_FROM_INDEX = 0  
DELAY_SECONDS = 60   # 1 minute safety buffer
# ---------------------

def get_conversation_text(conversation):
    """
    Claude format parser:
    Iterates through 'chat_messages' and extracts text content.
    """
    messages = []
    chat_messages = conversation.get('chat_messages', [])
    
    for msg in chat_messages:
        sender = msg.get('sender', 'unknown').upper()
        content_items = msg.get('content', [])
        
        text_parts = []
        for item in content_items:
            if item.get('type') == 'text':
                text_parts.append(item.get('text', ''))
        
        full_text = "".join(text_parts).strip()
        
        if full_text:
            # Format roles for the LLM
            role = "USER" if sender == "HUMAN" else "CLAUDE"
            messages.append(f"{role}: {full_text}")

    return "\n\n".join(messages)

def main():
    try:
        with open(FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {FILE_PATH} not found.")
        return

    total = len(data)
    print(f"Found {total} Claude conversations. Starting Ingestion...")
    print(f"Resuming from #{START_FROM_INDEX}...")

    for i, conv in enumerate(data):
        if i < START_FROM_INDEX:
            continue

        # 1. Extract Claude Transcript
        transcript = get_conversation_text(conv)
        
        if not transcript or len(transcript) < 10:
            print(f"[{i+1}/{total}] ⏩ Skipped (Empty): {conv.get('name')}")
            continue

        # Claude uses 'name' for title and 'created_at' for timestamp
        payload = {
            "title": conv.get('name', 'Untitled Chat'),
            "created_at": conv.get('created_at'), 
            "transcript": transcript,
            "conversation_id": conv.get('uuid')
        }

        # 2. Fire Request
        try:
            response = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=30)
            if response.status_code == 200:
                print(f"[{i+1}/{total}] 🚀 Sent: {payload['title']}")
            else:
                print(f"[{i+1}/{total}] ⚠️ Server error {response.status_code}")

        except Exception as e:
            print(f"[{i+1}/{total}] ❌ Connection error: {e}")
        
        # 3. Fixed Delay
        print(f"   ... Waiting {DELAY_SECONDS}s for n8n to finish ...")
        time.sleep(DELAY_SECONDS)

if __name__ == "__main__":
    main()