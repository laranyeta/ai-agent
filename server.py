from mcp.server.mcpserver import MCPServer

mcp = MCPServer("agente-empleo")

@mcp.tool()
def contar_palabra_en_ofertas(palabra: str) -> str:
    """Cuenta cuántas veces aparece una palabra (ej. una tecnología) en las ofertas guardadas."""
    # De momento, datos de ejemplo. Luego lo conectarás a tus archivos reales.
    ofertas_ejemplo = [
        "Se busca ML Engineer con experiencia en Docker y Kubernetes",
        "Data Scientist con Python, SQL y conocimientos de Kubernetes",
        "AI Engineer, se valora experiencia con agentic AI y MCP",
    ]
    texto = " ".join(ofertas_ejemplo).lower()
    apariciones = texto.count(palabra.lower())
    return f"La palabra '{palabra}' aparece {apariciones} veces en las ofertas guardadas."

if __name__ == "__main__":
    mcp.run(transport="stdio")
