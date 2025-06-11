"""Utility functions for RAG evaluation tests."""

from pathlib import Path
from typing import Dict

import pandas as pd


def generate_rag_html_report(
    df: pd.DataFrame,
    timestamp: str,
    samples_count: int,
    metric_summaries: Dict[str, float],
    output_path: Path,
) -> None:
    """
    Generate a searchable HTML report for RAG evaluation results.

    Args:
        df: DataFrame containing evaluation results
        timestamp: Timestamp string for the evaluation run
        samples_count: Number of samples evaluated
        metric_summaries: Dictionary of metric names and their average scores
        output_path: Path where the HTML file should be saved
    """

    # Generate HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>RAG Evaluation Results - {timestamp}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .metric {{ color: #2E86AB; font-weight: bold; }}
            .summary {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .sample-row:nth-child(even) {{ background-color: #f9f9f9; }}
            .response-cell {{ max-width: 300px; word-wrap: break-word; }}
            .search-container {{ margin: 20px 0; padding: 10px; background-color: #e9ecef; border-radius: 5px; }}
            .search-input {{ padding: 8px; width: 300px; border: 1px solid #ddd; border-radius: 4px; }}
            .metric-good {{ color: #28a745; }}
            .metric-fair {{ color: #ffc107; }}
            .metric-poor {{ color: #dc3545; }}
        </style>
    </head>
    <body>
        <h1>RAG Evaluation Results</h1>
        <div class="summary">
            <h2>Summary</h2>
            <p><strong>Timestamp:</strong> {timestamp}</p>
            <p><strong>Number of samples:</strong> {samples_count}</p>
            <p><strong>Evaluation framework:</strong> ragas</p>
            <h3>Metric Averages</h3>
            <ul>
    """

    # Add metric summaries with color coding
    for metric, avg_score in metric_summaries.items():
        color_class = (
            "metric-good"
            if avg_score >= 0.7
            else "metric-fair"
            if avg_score >= 0.5
            else "metric-poor"
        )
        html_content += f'<li><span class="metric {color_class}">{metric}:</span> {avg_score:.3f}</li>\n'

    html_content += """
            </ul>
        </div>
        
        <div class="search-container">
            <label for="searchInput">Search results: </label>
            <input type="text" id="searchInput" class="search-input" onkeyup="searchTable()" 
                   placeholder="Type to search in any column...">
            <button onclick="clearSearch()" style="margin-left: 10px; padding: 8px 12px;">Clear</button>
        </div>
        
        <h2>Detailed Results</h2>
        <table id="resultsTable">
            <thead>
                <tr>
    """

    # Add table headers
    for column in df.columns:
        html_content += f"<th>{column.replace('_', ' ').title()}</th>\n"

    html_content += """
                </tr>
            </thead>
            <tbody>
    """

    # Add table rows
    for _idx, row in df.iterrows():
        html_content += '<tr class="sample-row">\n'
        for column in df.columns:
            value = row[column]
            if column in ["response", "user_input", "retrieved_contexts"]:
                # Truncate long text but make it searchable with full content in title
                display_value = (
                    str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                )
                escaped_value = str(value).replace('"', "&quot;").replace("'", "&#39;")
                html_content += f'<td class="response-cell" title="{escaped_value}">{display_value}</td>\n'
            elif isinstance(value, float):
                # Color code metric scores
                if column in [
                    "faithfulness",
                    "answer_relevancy",
                    "context_precision",
                    "context_recall",
                ]:
                    color_class = (
                        "metric-good"
                        if value >= 0.7
                        else "metric-fair"
                        if value >= 0.5
                        else "metric-poor"
                    )
                    html_content += f'<td class="{color_class}">{value:.3f}</td>\n'
                else:
                    html_content += f"<td>{value:.3f}</td>\n"
            else:
                html_content += f"<td>{str(value)}</td>\n"
        html_content += "</tr>\n"

    html_content += """
            </tbody>
        </table>
        
        <script>
            // Make table searchable
            function searchTable() {
                const input = document.getElementById("searchInput");
                const filter = input.value.toLowerCase();
                const table = document.getElementById("resultsTable");
                const rows = table.getElementsByTagName("tr");
                
                for (let i = 1; i < rows.length; i++) {
                    const row = rows[i];
                    const cells = row.getElementsByTagName("td");
                    let found = false;
                    
                    for (let j = 0; j < cells.length; j++) {
                        const cellText = cells[j].textContent || cells[j].innerText;
                        const titleText = cells[j].getAttribute("title") || "";
                        if (cellText.toLowerCase().includes(filter) || titleText.toLowerCase().includes(filter)) {
                            found = true;
                            break;
                        }
                    }
                    
                    row.style.display = found ? "" : "none";
                }
            }
            
            function clearSearch() {
                document.getElementById("searchInput").value = "";
                searchTable();
            }
            
            // Add keyboard shortcut for search
            document.addEventListener('keydown', function(e) {
                if (e.ctrlKey && e.key === 'f') {
                    e.preventDefault();
                    document.getElementById("searchInput").focus();
                }
            });
        </script>
        
        <div style="margin-top: 30px; padding: 10px; background-color: #f8f9fa; border-radius: 5px; font-size: 0.9em;">
            <strong>Tips:</strong>
            <ul>
                <li>Use Ctrl+F to quickly focus the search box</li>
                <li>Search works across all columns including full text content</li>
                <li>Hover over truncated text to see the full content</li>
                <li>Scores are color-coded: <span class="metric-good">Green ≥ 0.7</span>, 
                    <span class="metric-fair">Yellow ≥ 0.5</span>, <span class="metric-poor">Red < 0.5</span></li>
            </ul>
        </div>
    </body>
    </html>
    """

    # Save HTML report
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)


def calculate_metric_summaries(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate summary statistics for metrics in the DataFrame.

    Args:
        df: DataFrame containing evaluation results

    Returns:
        Dictionary of metric names and their average scores
    """
    metric_summaries = {}
    excluded_columns = ["user_input", "retrieved_contexts", "response", "reference"]

    for column in df.columns:
        if column not in excluded_columns:
            values = df[column].dropna()
            if len(values) > 0 and pd.api.types.is_numeric_dtype(values):
                metric_summaries[column] = values.mean()

    return metric_summaries
