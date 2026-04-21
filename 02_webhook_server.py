"""
Script 2: Event-Driven App — Webhook Server

Demonstrates how to build an app that the Unique platform calls into.
When a user sends a message in the Unique chat UI and your "external module"
is selected, the platform sends a webhook to your server. Your server
processes the message and writes a response back.

This is the primary pattern for serving applications to end-users.

Usage:
    uv run python 02_webhook_server.py

Then expose this server (e.g., via ngrok for local dev) and register
the URL as your module's webhook endpoint in the Unique platform.
"""

import os
import threading
from http import HTTPStatus

from dotenv import load_dotenv
from flask import Flask, jsonify, request

import unique_sdk

load_dotenv()

unique_sdk.api_key = os.environ["UNIQUE_API_KEY"]
unique_sdk.app_id = os.environ["UNIQUE_APP_ID"]

ENDPOINT_SECRET = os.environ["UNIQUE_ENDPOINT_SECRET"]

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for container orchestrators."""
    return jsonify(status="ok"), HTTPStatus.OK


@app.route("/webhook", methods=["POST"])
def webhook():
    """
    Receives webhook events from the Unique platform.

    Two key event types:
      - unique.chat.user-message.created  → a user sent a message (for logging/analytics)
      - unique.chat.external-module.chosen → YOUR module was selected to respond
    """
    payload = request.data
    sig_header = request.headers.get("X-Unique-Signature")
    timestamp = request.headers.get("X-Unique-Created-At")

    if not sig_header or not timestamp:
        return jsonify(success=False, error="Missing signature headers"), HTTPStatus.BAD_REQUEST

    # Verify the webhook signature (HMAC-SHA256)
    try:
        event = unique_sdk.Webhook.construct_event(
            payload, sig_header, timestamp, ENDPOINT_SECRET
        )
    except unique_sdk.SignatureVerificationError:
        return jsonify(success=False, error="Invalid signature"), HTTPStatus.BAD_REQUEST

    # Route by event type
    event_type = event.event
    print(f"Received event: {event_type}")

    if event_type == "unique.chat.external-module.chosen":
        threading.Thread(target=handle_external_module, args=(event,)).start()
    elif event_type == "unique.chat.user-message.created":
        handle_user_message(event)
    else:
        print(f"Unhandled event type: {event_type}")

    return jsonify(success=True), HTTPStatus.OK


def handle_user_message(event):
    """Log when a user sends a message (useful for analytics)."""
    text = event.payload.text
    chat_id = event.payload.chatId
    print(f"[LOG] User message in chat {chat_id}: {text}")


def handle_external_module(event):
    """
    Core handler: the platform chose YOUR module to answer the user.

    Runs in a background thread (webhook already acknowledged with 200 OK).

    Steps:
      1. Read the user's message
      2. (Optional) Search the knowledge base for context
      3. Generate a response via ChatCompletion
      4. Write the response back to the assistant message
    """
    user_id = event.userId
    company_id = event.companyId
    chat_id = event.payload.chatid  # note: lowercase 'id' in this event
    user_text = event.payload.userMessage.text
    assistant_message_id = event.payload.assistantMessage.id

    print(f"[MODULE] Processing: '{user_text}'")

    open_logs = []

    try:
        # Step 1: Search knowledge base for relevant context
        search_log = unique_sdk.MessageLog.create(
            user_id=user_id,
            company_id=company_id,
            messageId=assistant_message_id,
            text="Searching knowledge base...",
            status="RUNNING",
            order=1,
        )
        open_logs.append(search_log)

        search_results = unique_sdk.Search.create(
            user_id=user_id,
            company_id=company_id,
            searchString=user_text,
            searchType="COMBINED",
            limit=3,
        )

        # Step 2: Build context from search results
        context_texts = []
        for result in search_results or []:
            text = getattr(result, "text", str(result))
            context_texts.append(text[:500])
        context = "\n---\n".join(context_texts) if context_texts else "No relevant documents found."

        num_results = len(search_results) if search_results else 0
        unique_sdk.MessageLog.update(
            user_id=user_id,
            company_id=company_id,
            message_log_id=search_log.id,
            text=f"Found {num_results} relevant documents",
            status="COMPLETED",
        )
        open_logs.remove(search_log)

        # Step 3: Generate response using the LLM
        completion_log = unique_sdk.MessageLog.create(
            user_id=user_id,
            company_id=company_id,
            messageId=assistant_message_id,
            text="Generating response...",
            status="RUNNING",
            order=2,
        )
        open_logs.append(completion_log)

        completion = unique_sdk.ChatCompletion.create(
            user_id=user_id,
            company_id=company_id,
            model="AZURE_GPT_4o_2024_0513",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant. Use the following context from "
                        "the company knowledge base to answer the user's question.\n\n"
                        f"Context:\n{context}"
                    ),
                },
                {"role": "user", "content": user_text},
            ],
            temperature=0.3,
        )
        response_text = completion.choices[0].message.content

        unique_sdk.MessageLog.update(
            user_id=user_id,
            company_id=company_id,
            message_log_id=completion_log.id,
            text="Response generated",
            status="COMPLETED",
        )
        open_logs.remove(completion_log)

        # Step 4: Write response back to the platform
        unique_sdk.Message.modify(
            user_id=user_id,
            company_id=company_id,
            id=assistant_message_id,
            chatId=chat_id,
            text=response_text,
        )
        print(f"[MODULE] Responded: '{response_text[:100]}...'")

    except Exception as e:
        print(f"[MODULE] Error processing message: {e}")
        for log in open_logs:
            unique_sdk.MessageLog.update(
                user_id=user_id,
                company_id=company_id,
                message_log_id=log.id,
                status="FAILED",
            )
        unique_sdk.Message.modify(
            user_id=user_id,
            company_id=company_id,
            id=assistant_message_id,
            chatId=chat_id,
            text="Sorry, something went wrong processing your request. Please try again.",
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
