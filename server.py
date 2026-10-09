"""MCP server exposing the user's saved job offers as tools.

The offers live in an Excel file with three columns:
    1. Puesto       -> role
    2. Empresa      -> company
    3. Descripcion  -> description

Run it directly for stdio transport:

    python server.py

IMPORTANT: a stdio MCP server must never write to stdout, because stdout
carries the JSON-RPC messages. All logging goes to stderr via `logging`.
"""

import logging

import openpyxl
from mcp.server import MCPServer

from config import OFFERS_FILE

logger = logging.getLogger(__name__)

mcp = MCPServer("job-offers")


def load_offers() -> list[tuple[str, str, str]]:
    """Read every non-empty offer row from the spreadsheet.

    Returns a list of (role, company, description) tuples. Missing cells are
    normalised to empty strings so callers never have to deal with None.

    Raises:
        FileNotFoundError: if the spreadsheet does not exist.
    """
    workbook = openpyxl.load_workbook(OFFERS_FILE, read_only=True, data_only=True)
    sheet = workbook.active

    offers = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        # Pad or trim so unpacking never fails on a malformed row.
        role, company, description = (list(row) + [None, None, None])[:3]
        if not role:
            continue
        offers.append((str(role), str(company or ""), str(description or "")))

    workbook.close()
    logger.info("Loaded %d offers from %s", len(offers), OFFERS_FILE)
    return offers


def format_offer(offer: tuple[str, str, str]) -> str:
    """Render one offer as readable Markdown for the model."""
    role, company, description = offer
    header = f"**{role}**" + (f" at {company}" if company else "")
    return f"{header}\n{description}" if description else header


@mcp.tool()
def get_offers() -> str:
    """List every job offer the user has saved, with role, company and description.

    Use this when the user asks what offers they have, wants an overview, or
    asks a question that needs all the offers at once.
    """
    try:
        offers = load_offers()
    except FileNotFoundError:
        return f"[ERROR] The offers file was not found at {OFFERS_FILE}."

    if not offers:
        return "No saved offers have been found."

    return "\n\n---\n\n".join(format_offer(offer) for offer in offers)


@mcp.tool()
def get_keyword(keyword: str) -> str:
    """Return the saved offers whose role or description contains a keyword.

    Use this to narrow the search instead of loading every offer, for example
    when the user asks about a technology ("which offers need Kubernetes?"),
    a company, or a kind of role.

    Args:
        keyword: Word or phrase to look for. Case-insensitive.
    """
    try:
        offers = load_offers()
    except FileNotFoundError:
        return f"[ERROR] The offers file was not found at {OFFERS_FILE}."

    word = keyword.lower()
    found = [
        offer
        for offer in offers
        if word in offer[0].lower()
        or word in offer[1].lower()
        or word in offer[2].lower()
    ]

    if not found:
        return f"No offers containing '{keyword}' have been found."

    return "\n\n---\n\n".join(format_offer(offer) for offer in found)


@mcp.tool()
def count_keyword(keyword: str) -> str:
    """Count how many saved offers mention a keyword, and how often in total.

    Use this for frequency questions, such as which technologies come up most
    across the offers the user is tracking.

    Args:
        keyword: Word or phrase to count. Case-insensitive.
    """
    try:
        offers = load_offers()
    except FileNotFoundError:
        return f"[ERROR] The offers file was not found at {OFFERS_FILE}."

    word = keyword.lower()
    matching_offers = 0
    total_mentions = 0

    for role, company, description in offers:
        text = f"{role} {company} {description}".lower()
        mentions = text.count(word)
        if mentions:
            matching_offers += 1
            total_mentions += mentions

    return (
        f"'{keyword}' appears {total_mentions} time(s) "
        f"across {matching_offers} of {len(offers)} saved offers."
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)  # logging writes to stderr
    mcp.run(transport="stdio")
