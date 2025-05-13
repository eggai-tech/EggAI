"""Metrics for evaluating billing agent responses."""

import re
from typing import Tuple


def get_amount_score(expected: str, actual: str) -> Tuple[float, bool]:
    """Evaluate money amount matching between expected and actual responses."""
    try:
        # Extract amount in various formats ($300.00, $300, etc.)
        expected_amount_match = re.search(r'\$(\d+(?:\.\d+)?)', expected)
        expected_amount = expected_amount_match.group(1) if expected_amount_match else None
        
        if not expected_amount:
            return (0.5, True) if "$" in actual else (0.0, False)
            
        # Try to find the same amount in various formats
        amount_patterns = [
            fr'\${expected_amount}',  # $300.00
            fr'\$\s*{expected_amount}',  # $ 300.00
            fr'\${expected_amount.split(".")[0]}',  # $300
            fr'\${int(float(expected_amount)):,}',  # $300 with commas if needed
        ]
        
        # Check each pattern
        for pattern in amount_patterns:
            if re.search(pattern, actual):
                return (1.0, True)
                
        # If amount not found but $ is present, partial credit
        return (0.5, True) if "$" in actual else (0.0, True)
    except (IndexError, ValueError):
        # If $ is present in both, partial credit
        return (0.5, True) if "$" in actual else (0.0, True)


def get_date_score(expected: str, actual: str) -> Tuple[float, bool]:
    """Evaluate date matching between expected and actual responses."""
    date_formats = ["2026-02-01", "2026-03-15", "2026-12-01"]
    
    for date in date_formats:
        if date not in expected:
            continue
            
        # Full date exact match
        if date in actual:
            return (1.0, True)
        
        # Extract components for partial matching
        year, month, day = date.split("-")
        
        # Various date formats
        date_patterns = [
            f"{month}/{day}/{year}",  # 03/15/2026
            f"{month}-{day}-{year}",  # 03-15-2026
            f"{month}.{day}.{year}",  # 03.15.2026
            f"{year}-{month}",        # 2026-03 (partial)
            f"{month}/{year}",        # 03/2026 (partial)
            f"{month} {year}",        # March 2026
        ]
        
        # Check for any date pattern
        for pattern in date_patterns:
            if pattern in actual:
                return (0.8, True)  # Almost full credit for alternative formats
                
        # Check for month names if numerical didn't match
        month_names = {
            "01": ["january", "jan"],
            "02": ["february", "feb"],
            "03": ["march", "mar"],
            "04": ["april", "apr"],
            "05": ["may"],
            "06": ["june", "jun"],
            "07": ["july", "jul"],
            "08": ["august", "aug"],
            "09": ["september", "sep", "sept"],
            "10": ["october", "oct"],
            "11": ["november", "nov"],
            "12": ["december", "dec"]
        }
        
        if month in month_names:
            for month_name in month_names[month]:
                if month_name in actual and year in actual:
                    return (0.7, True)  # Good credit for month name + year
            
        # Basic year matching
        if year in actual:
            return (0.3, True)  # Minimal credit for just the year
    
    return (0.0, False)  # No date match found


def get_status_score(expected: str, actual: str) -> Tuple[float, bool]:
    """Evaluate status matching between expected and actual responses."""
    if "status is" not in expected and "'status':" not in expected:
        return (0.0, False)
        
    try:
        # Extract status using different patterns
        status_patterns = [
            r"status is ['\"]([^'\"]+)['\"]",  # status is 'Pending'
            r"status:? ['\"]?([^'\",.]+)['\"]?",  # status: Pending or status: "Pending"
            r"status:? ([^,\.]+)",  # status: Pending (no quotes)
            r"your status is ([^,\.]+)",  # your status is Pending
            r"current status is ([^,\.]+)",  # current status is Pending
        ]
        
        expected_status = None
        for pattern in status_patterns:
            match = re.search(pattern, expected)
            if match:
                expected_status = match.group(1).strip().lower()
                break
        
        if expected_status:
            # Check for status in actual response
            if expected_status in actual:
                return (1.0, True)
            elif "status" in actual:
                # Check if any word after "status" matches expected status approximately
                status_words = re.findall(r"status\W+(\w+)", actual)
                for word in status_words:
                    if (word.lower() == expected_status or 
                        word.lower() in expected_status or 
                        expected_status in word.lower()):
                        return (0.8, True)
                return (0.5, True)  # Status mentioned but different
        else:
            # Couldn't extract expected status, give partial credit if status mentioned
            if "status" in actual:
                return (0.5, True)
    except Exception:
        # Fallback - give partial credit if status is mentioned
        if "status" in actual:
            return (0.5, True)
            
    return (0.0, False)  # No status match


def get_billing_cycle_score(expected: str, actual: str) -> Tuple[float, bool]:
    """Evaluate billing cycle matching between expected and actual responses."""
    if "billing cycle" not in expected:
        return (0.0, False)
        
    # Try to extract cycle type
    cycle_types = ["annual", "monthly", "quarterly", "bi-monthly", "weekly"]
    expected_cycle = None
    
    # Find which cycle type is in expected
    for cycle in cycle_types:
        if cycle in expected.lower():
            expected_cycle = cycle
            break
    
    # Check for cycle in actual
    if "billing cycle" in actual and expected_cycle and expected_cycle in actual:
        return (1.0, True)  # Full match - both billing cycle and type
    elif "billing cycle" in actual:
        return (0.8, True)  # Billing cycle mentioned but type may differ
    elif "cycle" in actual and expected_cycle and expected_cycle in actual:
        return (0.7, True)  # Cycle type matches but not specifically "billing cycle"
    elif "cycle" in actual:
        return (0.5, True)  # Just "cycle" mentioned
    elif expected_cycle and expected_cycle in actual:
        return (0.3, True)  # Just cycle type mentioned
        
    return (0.0, False)  # No billing cycle match


def get_format_score(expected: str, actual: str) -> Tuple[float, bool]:
    """Evaluate format consistency between expected and actual responses."""
    format_score = 0.0
    format_checks = 0
    
    # Date format consistency
    if "2026" in expected and "2026" in actual:
        format_checks += 1
        # Check if using YYYY-MM-DD format consistently
        if re.search(r'20\d\d-\d\d-\d\d', expected) and re.search(r'20\d\d-\d\d-\d\d', actual):
            format_score += 1.0
        else:
            format_score += 0.5  # Date present but format differs
    
    # Dollar format consistency
    if "$" in expected and "$" in actual:
        format_checks += 1
        # Check if using $X.XX format
        if re.search(r'\$\d+\.\d\d', expected) and re.search(r'\$\d+\.\d\d', actual):
            format_score += 1.0
        else:
            format_score += 0.5  # Dollar present but format differs
    
    # Add format score if we checked anything
    if format_checks > 0:
        return (format_score / format_checks, True)
        
    return (0.0, False)  # No format checks performed


def precision_metric(expected_str: str, actual_str: str) -> float:
    """Calculate precision score by comparing expected and predicted responses."""
    expected = expected_str.lower()
    actual = actual_str.lower()
    
    score = 0.0
    check_count = 0
    
    # Run all evaluations
    evaluations = [
        get_amount_score(expected, actual),
        get_date_score(expected, actual),
        get_status_score(expected, actual),
        get_billing_cycle_score(expected, actual),
        get_format_score(expected, actual)
    ]
    
    # Aggregate results
    for eval_score, eval_performed in evaluations:
        if eval_performed:
            score += eval_score
            check_count += 1
    
    # Calculate overall score
    if check_count == 0:
        return 0.0
        
    return score / check_count