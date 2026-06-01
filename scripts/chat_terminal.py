#!/usr/bin/env python3
"""Terminal REPL to exercise orchestrator handle_transcript (emergency gate + chat)."""

import asyncio
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

# Project root on path when run as script
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
load_dotenv(_ROOT / ".env")

from src.orchestrator import clear_session, handle_transcript, start_session


async def main() -> None:
    session_id = str(uuid.uuid4())
    start_session(session_id)
    print("Mercy General orchestrator terminal (Ctrl+C or 'quit' to exit)")
    print(f"session_id={session_id}\n")

    try:
        while True:
            try:
                line = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not line:
                continue
            if line.lower() in {"quit", "exit", "q"}:
                break

            reply = await handle_transcript(
                {"session_id": session_id, "text": line, "type": "transcript.final"}
            )
            if reply:
                print(f"Agent: {reply}\n")
            else:
                print("Agent: (no reply — session ended)\n")
    finally:
        clear_session(session_id)
        print("Session cleared.")


if __name__ == "__main__":
    asyncio.run(main())
