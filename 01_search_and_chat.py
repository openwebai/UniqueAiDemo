"""
Script 1: Standalone App — Search & Chat Completion

Demonstrates the two most fundamental SDK operations:
  1. Searching the knowledge base (vector + keyword search)
  2. Generating a chat completion (LLM call through Unique's proxy)

This is a "standalone" app — it runs locally, hits the API, and prints results.
No webhook or server needed.

Usage:
    uv run python 01_search_and_chat.py
"""

import os

from dotenv import load_dotenv

import unique_sdk

load_dotenv()

unique_sdk.api_key = os.environ["UNIQUE_API_KEY"]
unique_sdk.app_id = os.environ["UNIQUE_APP_ID"]

USER_ID = os.environ["UNIQUE_USER_ID"]
COMPANY_ID = os.environ["UNIQUE_COMPANY_ID"]


def search_knowledge_base(query: str, limit: int = 5):
    """Search the company knowledge base using combined vector + keyword search."""
    print(f"\n--- Searching knowledge base for: '{query}' ---")
    results = unique_sdk.Search.create(
        user_id=USER_ID,
        company_id=COMPANY_ID,
        searchString=query,
        searchType="COMBINED",
        limit=limit,
    )
    if not results:
        print("No results found.")
        return []

    for i, result in enumerate(results, 1):
        print(f"\n  [{i}] Score: {getattr(result, 'score', 'N/A')}")
        text = getattr(result, "text", str(result))
        print(f"      {text[:200]}...")
    return results


def chat_completion(user_message: str, model: str = "AZURE_GPT_4o_2024_0513"):
    """Generate a chat completion through Unique's LLM proxy."""
    print(f"\n--- Chat completion (model: {model}) ---")
    print(f"  User: {user_message}")

    response = unique_sdk.ChatCompletion.create(
        user_id=USER_ID,
        company_id=COMPANY_ID,
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_message},
        ],
        temperature=0.7,
    )
    answer = response.choices[0].message.content
    print(f"  Assistant: {answer}")
    return answer


if __name__ == "__main__":
    # 1. Search the knowledge base
    search_knowledge_base("quarterly report")

    # 2. Generate a chat completion
    chat_completion("Summarize what Unique AI does in one paragraph.")
