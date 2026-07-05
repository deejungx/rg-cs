def collect_stats(content: str) -> dict[str, int]:
    return {
        "characters": len(content),
        "words": len(content.split()),
        "lines": len(content.splitlines()),
    }
