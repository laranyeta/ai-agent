"""Terminal chat with the job hunting agent.

Same agent as the web interface, without the HTTP layer. Useful for a quick
check that the MCP connection and the tool loop work.

    python chat.py
"""

import asyncio
import logging
import sys

from agent import JobHuntingAgent

BOLD, DIM, ORANGE, RESET = "\033[1m", "\033[2m", "\033[38;5;173m", "\033[0m"


async def main() -> None:
    logging.basicConfig(level=logging.WARNING)

    print(f"{DIM}Connecting to the MCP server…{RESET}")
    async with JobHuntingAgent() as agent:
        names = ", ".join(tool["name"] for tool in agent.tools)
        print(f"{BOLD}Job Hunting Agent{RESET}  {DIM}tools: {names}{RESET}")
        print(f"{DIM}Type 'quit' to exit, 'reset' to clear the conversation.{RESET}\n")

        history: list = []

        while True:
            try:
                question = (await asyncio.to_thread(input, f"{BOLD}you ›{RESET} ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not question:
                continue
            if question.lower() in {"quit", "exit"}:
                break
            if question.lower() == "reset":
                history.clear()
                print(f"{DIM}Conversation cleared.{RESET}\n")
                continue

            try:
                result = await agent.ask(question, history)
            except Exception as error:  # noqa: BLE001 - keep the session alive
                print(f"{ORANGE}Error: {error}{RESET}\n", file=sys.stderr)
                continue

            if result["tools_used"]:
                used = ", ".join(f"{name}()" for name in dict.fromkeys(result["tools_used"]))
                print(f"{DIM}· called {used}{RESET}")
            print(f"{ORANGE}agent ›{RESET} {result['reply']}\n")

    print(f"{DIM}Bye.{RESET}")


if __name__ == "__main__":
    asyncio.run(main())
