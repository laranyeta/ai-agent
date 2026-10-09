"""The job hunting agent: RAG over the CV plus tool calling over MCP.

Flow of one question:

    question
      -> retrieve the most relevant CV chunks from Chroma (RAG)
      -> send question + CV context + MCP tool schemas to Claude
      -> while Claude asks for tools: run them through the MCP server,
         send the results back
      -> return Claude's final answer

The job offers are NOT stuffed into the prompt. They are reached through the
MCP tools only when the model decides it needs them, which is what keeps the
prompt small as the spreadsheet grows.
"""

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Any

from anthropic import AsyncAnthropic
from mcp import Client, StdioServerParameters
from mcp_types import TextContent

from config import (
    MAX_HISTORY_MESSAGES,
    MAX_TOKENS,
    MAX_TOOL_ROUNDS,
    MODEL,
    N_RESULTS,
    SERVER_SCRIPT,
    SYSTEM_PROMPT,
    get_collection,
)

logger = logging.getLogger(__name__)


class JobHuntingAgent:
    """Holds the Claude client, the vector store and the live MCP connection.

    Use it as an async context manager so the MCP server subprocess is started
    once and reused across questions:

        async with JobHuntingAgent() as agent:
            answer = await agent.ask("Which offers match my CV?")
    """

    def __init__(self) -> None:
        self.claude = AsyncAnthropic()
        self.collection = get_collection()
        self.client: Client | None = None
        self.tools: list[dict[str, Any]] = []
        self._stack = AsyncExitStack()

    # --- lifecycle ---------------------------------------------------------

    async def __aenter__(self) -> "JobHuntingAgent":
        await self.connect()
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.close()

    async def connect(self) -> None:
        """Start the MCP server subprocess and load its tool schemas."""
        params = StdioServerParameters(
            command="python",
            args=[str(SERVER_SCRIPT)],
        )
        self.client = await self._stack.enter_async_context(Client(params))

        tool_list = await self.client.list_tools()
        self.tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in tool_list.tools
        ]
        logger.info("Connected to MCP server. Tools: %s", [t["name"] for t in self.tools])

    async def close(self) -> None:
        """Shut the MCP connection and its subprocess down."""
        await self._stack.aclose()
        self.client = None

    # --- RAG ---------------------------------------------------------------

    def get_context(self, query: str, n_results: int = N_RESULTS) -> str:
        """Return the CV chunks most similar to the query, joined as one string."""
        results = self.collection.query(query_texts=[query], n_results=n_results)
        documents = results.get("documents") or [[]]
        fragments = documents[0]
        if not fragments:
            return "No CV documents have been indexed yet. Run: python index.py"
        return "\n\n---\n\n".join(fragments)

    # --- tool calling ------------------------------------------------------

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        """Run one MCP tool and return (text result, is_error).

        A failing tool does not raise: MCP answers with is_error set, and
        passing that flag on lets Claude read the message and recover.
        """
        result = await self.client.call_tool(name, arguments)
        text = "\n".join(
            block.text for block in result.content if isinstance(block, TextContent)
        )
        return text or "(the tool returned no text)", bool(result.is_error)

    # --- main entry point --------------------------------------------------

    async def ask(
        self,
        query: str,
        history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Answer one question, running any tools Claude asks for.

        Args:
            query: The user's question.
            history: Previous messages, in Anthropic format. Mutated in place
                so the caller keeps the running conversation.

        Returns:
            {"reply": str, "tools_used": list[str]}
        """
        if self.client is None:
            raise RuntimeError("Agent is not connected. Use `async with JobHuntingAgent()`.")

        messages = history if history is not None else []

        # The CV context rides along with the question itself, so earlier turns
        # in the history keep the context they were answered with.
        context = self.get_context(query)
        messages.append(
            {
                "role": "user",
                "content": f"CV context:\n{context}\n\nQuestion: {query}",
            }
        )

        tools_used: list[str] = []

        for _ in range(MAX_TOOL_ROUNDS):
            response = await self.claude.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=self.tools,
                messages=messages,
            )

            usage = getattr(response, "usage", None)
            logger.info(
                "stop_reason=%s input_tokens=%s output_tokens=%s",
                response.stop_reason,
                getattr(usage, "input_tokens", "?"),
                getattr(usage, "output_tokens", "?"),
            )

            # Hitting the output cap mid-answer leaves a truncated reply, and if
            # it lands mid tool_use, a block too incomplete to send back. Keep
            # only the finished text so the history stays valid, and say so.
            if response.stop_reason == "max_tokens":
                text_blocks = [b for b in response.content if b.type == "text"]
                reply = "\n".join(b.text for b in text_blocks).strip()
                messages.append(
                    {
                        "role": "assistant",
                        "content": text_blocks
                        or [{"type": "text", "text": "(no answer produced)"}],
                    }
                )
                self._trim(messages)
                note = (
                    f"\n\n[Cut off at the {MAX_TOKENS}-token limit. "
                    f"Ask for a shorter answer, or raise MAX_TOKENS in .env.]"
                )
                return {
                    "reply": (reply + note) if reply else note.strip(),
                    "tools_used": tools_used,
                }

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                reply = "\n".join(
                    block.text for block in response.content if block.type == "text"
                ).strip()
                self._trim(messages)
                return {
                    "reply": reply or "(the model returned an empty answer)",
                    "tools_used": tools_used,
                }

            # Claude asked for one or more tools: run them all, then loop.
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                logger.info("Calling tool %s with %s", block.name, block.input)
                tools_used.append(block.name)
                text, is_error = await self.call_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": text,
                        "is_error": is_error,
                    }
                )
            messages.append({"role": "user", "content": tool_results})

        self._trim(messages)
        return {
            "reply": (
                "I stopped after too many tool calls without reaching an answer. "
                "Try asking something more specific."
            ),
            "tools_used": tools_used,
        }

    @staticmethod
    def _trim(messages: list[dict[str, Any]]) -> None:
        """Keep the history bounded, without splitting a tool_use/tool_result pair."""
        while len(messages) > MAX_HISTORY_MESSAGES:
            messages.pop(0)
            # A history must not start with a tool result orphaned from its call.
            while messages and _is_tool_result(messages[0]):
                messages.pop(0)


def _is_tool_result(message: dict[str, Any]) -> bool:
    content = message.get("content")
    return (
        isinstance(content, list)
        and bool(content)
        and isinstance(content[0], dict)
        and content[0].get("type") == "tool_result"
    )


async def _demo() -> None:
    """Answer a single hardcoded question. Useful as a smoke test."""
    logging.basicConfig(level=logging.INFO)
    async with JobHuntingAgent() as agent:
        result = await agent.ask("Which technologies come up most in my saved offers?")
        print(result["reply"])


if __name__ == "__main__":
    asyncio.run(_demo())
