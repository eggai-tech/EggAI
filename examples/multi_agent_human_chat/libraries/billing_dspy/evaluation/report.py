"""Report generation utilities for billing agent test results."""

from typing import List


def markdown_table(rows: List[List[str]], headers: List[str]) -> str:
    """Generate a markdown table from rows and headers."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def _fmt_row(cells):
        return (
            "| "
            + " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells))
            + " |"
        )

    sep = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    lines = [_fmt_row(headers), sep]
    lines += [_fmt_row(r) for r in rows]
    return "\n".join(lines)


def generate_test_report(test_results):
    """Generate a markdown report from test results."""
    headers = [
        "ID",
        "Policy",
        "Expected",
        "Response",
        "Latency",
        "LLM ✓",
        "LLM Prec",
        "Calc Prec",
        "Reasoning",
    ]
    rows = [
        [
            r["id"],
            r["policy"],
            r["expected"],
            r["response"],
            r["latency"],
            r["judgment"],
            r["precision"],
            r["calc_precision"],
            r["reasoning"],
        ]
        for r in test_results
    ]
    return markdown_table(rows, headers)


def generate_module_test_report(test_results):
    """Generate a markdown report from module test results."""
    headers = ["ID", "Policy", "Expected", "Response", "Latency", "Precision", "Result"]
    rows = [
        [
            r["id"],
            r["policy"],
            r["expected"],
            r["response"],
            r["latency"],
            r["precision"],
            r["result"],
        ]
        for r in test_results
    ]
    return markdown_table(rows, headers)
