"""
Script 3: Space API — Programmatic Interaction

Demonstrates how to interact with a pre-configured space via the SDK.
Instead of orchestrating search + LLM calls yourself, you send a message
to a space and let the platform handle the full pipeline (routing, search,
LLM call) based on the space's UI configuration.

Usage:
    uv run python 03_space_api.py
"""

import os
import sys

import httpx
from dotenv import load_dotenv

import unique_sdk

load_dotenv()

unique_sdk.api_key = os.environ["UNIQUE_API_KEY"]
unique_sdk.app_id = os.environ["UNIQUE_APP_ID"]

USER_ID = os.environ["UNIQUE_USER_ID"]
COMPANY_ID = os.environ["UNIQUE_COMPANY_ID"]

# The assistant ID for the space you want to interact with.
# Find this in the Unique platform UI or via Space.get_space().
ASSISTANT_ID = os.environ.get("UNIQUE_ASSISTANT_ID", "assistant_...")


def get_space_info(space_id: str):
    """Retrieve and display space configuration."""
    print(f"\n--- Space info: {space_id} ---")
    space = unique_sdk.Space.get_space(
        user_id=USER_ID,
        company_id=COMPANY_ID,
        space_id=space_id,
    )
    print(f"  Name: {space.name}")
    print(f"  Language model: {space.languageModel}")
    print(f"  Chat upload: {space.chatUpload}")
    print(f"  Modules: {[m['name'] for m in space.modules]}")
    return space


def start_chat(title: str = "SDK Demo Chat"):
    """Create a new chat session in the space."""
    print(f"\n--- Creating chat: '{title}' ---")
    chat = unique_sdk.Space.create_chat(
        user_id=USER_ID,
        company_id=COMPANY_ID,
        title=title,
        assistantId=ASSISTANT_ID,
    )
    print(f"  Chat ID: {chat['id']}")
    return chat


def send_message(chat_id: str, text: str):
    """Send a message to the space and get the assistant's response."""
    print(f"\n--- Sending message ---")
    print(f"  User: {text}")
    response = unique_sdk.Space.create_message(
        user_id=USER_ID,
        company_id=COMPANY_ID,
        assistantId=ASSISTANT_ID,
        chatId=chat_id,
        text=text,
    )
    assistant_text = response.get("text", "")
    print(f"  Assistant: {assistant_text}")
    return response


def upload_document(chat_id: str, file_path: str):
    """
    Upload a document (e.g. PDF) into a chat for the space to use as context.

    Steps:
      1. Upsert content scoped to the chat — platform returns a writeUrl
      2. Upload the file bytes to that writeUrl
      3. The platform ingests the document (parse, chunk, embed)
    """
    file_name = os.path.basename(file_path)
    mime_type = "application/pdf" if file_name.endswith(".pdf") else "application/octet-stream"

    print(f"\n--- Uploading document: {file_name} ---")

    # Step 1: Create the content record scoped to this chat
    content = unique_sdk.Content.upsert(
        user_id=USER_ID,
        company_id=COMPANY_ID,
        chatId=chat_id,
        input={
            "key": file_name,
            "title": file_name,
            "mimeType": mime_type,
        },
    )

    write_url = content.writeUrl
    if not write_url:
        print("  Error: no writeUrl returned")
        return None

    # Step 2: Upload the actual file bytes
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    response = httpx.put(
        write_url,
        content=file_bytes,
        headers={"Content-Type": mime_type, "x-ms-blob-type": "BlockBlob"},
    )
    response.raise_for_status()

    print(f"  Uploaded {len(file_bytes)} bytes")
    print(f"  Content ID: {content.id}")
    return content


def get_history(chat_id: str):
    """Retrieve the full message history for a chat."""
    print(f"\n--- Chat history ---")
    result = unique_sdk.Space.get_chat_messages(
        user_id=USER_ID,
        company_id=COMPANY_ID,
        chat_id=chat_id,
    )
    for msg in result["messages"]:
        role = msg["role"]
        text = msg.get("text") or "(empty)"
        print(f"  [{role}] {text[:200]}")
    return result


if __name__ == "__main__":
    # 1. Start a new chat
    chat = start_chat("Q&A Session")
    chat_id = chat["id"]

    # 2. Upload a PDF into the chat (pass file path as CLI arg, or use default)
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
    if pdf_path:
        upload_document(chat_id, pdf_path)
        # 3. Ask questions about the uploaded document
        send_message(chat_id, "Summarize the document I just uploaded.")
        send_message(chat_id, "What are the key takeaways?")
    else:
        # No document — just interact with the knowledge base
        send_message(chat_id, "What documents are available in the knowledge base?")
        send_message(chat_id, "Summarize the most recent one.")

    # 4. Review the full conversation
    get_history(chat_id)
