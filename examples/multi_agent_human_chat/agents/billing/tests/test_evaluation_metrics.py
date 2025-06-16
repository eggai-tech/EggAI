"""Tests for billing evaluation metrics."""

import pytest

from agents.billing.dspy_modules.evaluation.metrics import (
    get_amount_score,
    get_billing_cycle_score,
    get_date_score,
    get_format_score,
    get_status_score,
    precision_metric,
)


def test_get_amount_score_exact_match():
    """Test amount score with exact match."""
    expected = "Your amount due is $120.50"
    actual = "Your amount due is $120.50"

    score, performed = get_amount_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(1.0)


def test_get_amount_score_different_format():
    """Test amount score with different format but same value."""
    expected = "Your amount due is $120.50"
    actual = "You owe $120.5"

    score, performed = get_amount_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(0.8)


def test_get_amount_score_wrong_amount():
    """Test amount score with wrong amount."""
    expected = "Your amount due is $120.50"
    actual = "Your amount due is $150.00"

    score, performed = get_amount_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(0.0)


def test_get_amount_score_no_amount():
    """Test amount score when no amount in expected."""
    expected = "Your status is active"
    actual = "Your amount due is $120.50"

    score, performed = get_amount_score(expected, actual)
    assert performed is False
    assert score == pytest.approx(0.0)


def test_get_date_score_exact_match():
    """Test date score with exact match."""
    expected = "Due date is 2026-05-15"
    actual = "Due date is 2026-05-15"

    score, performed = get_date_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(1.0)


def test_get_date_score_different_format():
    """Test date score with different format."""
    expected = "Due date is 2026-05-15"
    actual = "Due on May 15, 2026"

    score, performed = get_date_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(0.7)


def test_get_date_score_wrong_date():
    """Test date score with wrong date."""
    expected = "Due date is 2026-05-15"
    actual = "Due date is 2026-06-15"

    score, performed = get_date_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(0.0)


def test_get_date_score_no_date():
    """Test date score when no date in expected."""
    expected = "Your status is active"
    actual = "Due date is 2026-05-15"

    score, performed = get_date_score(expected, actual)
    assert performed is False
    assert score == pytest.approx(0.0)


def test_get_status_score_exact_match():
    """Test status score with exact match."""
    expected = "Your status is 'Paid'"
    actual = "Your status is 'Paid'"

    score, performed = get_status_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(1.0)


def test_get_status_score_different_quotes():
    """Test status score with different quote styles."""
    expected = "Your status is 'Paid'"
    actual = 'Your status is "Paid"'

    score, performed = get_status_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(0.9)


def test_get_status_score_no_quotes():
    """Test status score without quotes."""
    expected = "Your status is 'Paid'"
    actual = "Your status is Paid"

    score, performed = get_status_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(0.8)


def test_get_status_score_wrong_status():
    """Test status score with wrong status."""
    expected = "Your status is 'Paid'"
    actual = "Your status is 'Pending'"

    score, performed = get_status_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(0.0)


def test_get_status_score_no_status():
    """Test status score when no status in expected."""
    expected = "Your amount is $120.50"
    actual = "Your status is 'Paid'"

    score, performed = get_status_score(expected, actual)
    assert performed is False
    assert score == pytest.approx(0.0)


def test_get_billing_cycle_score_exact_match():
    """Test billing cycle score with exact match."""
    expected = "Your billing cycle is 'Monthly'"
    actual = "Your billing cycle is 'Monthly'"

    score, performed = get_billing_cycle_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(1.0)


def test_get_billing_cycle_score_partial_match():
    """Test billing cycle score with partial match."""
    expected = "Your billing cycle is 'Monthly'"
    actual = "Your billing cycle is different"

    score, performed = get_billing_cycle_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(0.8)


def test_get_billing_cycle_score_cycle_only():
    """Test billing cycle score with just 'cycle' mentioned."""
    expected = "Your billing cycle is 'Monthly'"
    actual = "Your cycle type is monthly"

    score, performed = get_billing_cycle_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(0.7)


def test_get_billing_cycle_score_type_only():
    """Test billing cycle score with just cycle type."""
    expected = "Your billing cycle is 'Monthly'"
    actual = "You are billed monthly"

    score, performed = get_billing_cycle_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(0.3)


def test_get_billing_cycle_score_no_match():
    """Test billing cycle score with no match."""
    expected = "Your billing cycle is 'Monthly'"
    actual = "Your status is active"

    score, performed = get_billing_cycle_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(0.0)


def test_get_billing_cycle_score_no_cycle():
    """Test billing cycle score when no cycle in expected."""
    expected = "Your status is active"
    actual = "Your billing cycle is 'Monthly'"

    score, performed = get_billing_cycle_score(expected, actual)
    assert performed is False
    assert score == pytest.approx(0.0)


def test_get_format_score_perfect_format():
    """Test format score with perfect format."""
    expected = "Your current amount due is $120.50 with a due date of 2026-05-15. Your status is 'Paid'."
    actual = "Your current amount due is $120.50 with a due date of 2026-05-15. Your status is 'Paid'."

    score, performed = get_format_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(1.0)


def test_get_format_score_partial_format():
    """Test format score with partial format match."""
    expected = "Your current amount due is $120.50 with a due date of 2026-05-15."
    actual = "Amount due: $120.50, due: 2026-05-15"

    score, performed = get_format_score(expected, actual)
    assert performed is True
    assert score > 0.0
    assert score < 1.0


def test_get_format_score_no_format():
    """Test format score when no format keywords in expected."""
    expected = "Hello there"
    actual = "Your current amount due is $120.50"

    score, performed = get_format_score(expected, actual)
    assert performed is False
    assert score == pytest.approx(0.0)


def test_precision_metric_all_evaluations():
    """Test precision metric with all evaluation types."""
    expected = "Your current amount due is $120.50 with a due date of 2026-05-15. Your status is 'Paid'. Your billing cycle is 'Monthly'."
    actual = "Your current amount due is $120.50 with a due date of 2026-05-15. Your status is 'Paid'. Your billing cycle is 'Monthly'."

    score = precision_metric(expected, actual)
    assert score == pytest.approx(1.0)


def test_precision_metric_partial_match():
    """Test precision metric with partial matches."""
    expected = "Your current amount due is $120.50 with a due date of 2026-05-15."
    actual = "Amount: $120.50, due: 2026-06-15"  # Wrong date

    score = precision_metric(expected, actual)
    assert 0.0 < score < 1.0


def test_precision_metric_no_evaluations():
    """Test precision metric when no evaluations are performed."""
    expected = "Hello there"
    actual = "Hi back"

    score = precision_metric(expected, actual)
    assert score == pytest.approx(0.0)


def test_precision_metric_mixed_results():
    """Test precision metric with mixed evaluation results."""
    expected = "Your amount due is $120.50 and status is 'Paid'"
    actual = "Your amount due is $150.00 and status is 'Paid'"  # Wrong amount, correct status

    score = precision_metric(expected, actual)
    assert 0.0 < score < 1.0


def test_amount_score_edge_cases():
    """Test amount score edge cases."""
    # Multiple amounts in text
    expected = "First amount $100.00 and second amount $200.00"
    actual = "First amount $100.00 and second amount $200.00"

    score, performed = get_amount_score(expected, actual)
    assert performed is True
    assert score > 0.0

    # Amount with commas
    expected = "Amount due is $1,234.56"
    actual = "Amount due is $1,234.56"

    score, performed = get_amount_score(expected, actual)
    assert performed is True
    assert score == pytest.approx(1.0)


def test_date_score_edge_cases():
    """Test date score edge cases."""
    # Multiple dates
    expected = "Start date 2026-01-01 and end date 2026-12-31"
    actual = "Start date 2026-01-01 and end date 2026-12-31"

    score, performed = get_date_score(expected, actual)
    assert performed is True
    assert score > 0.0

    # Date with different separators
    expected = "Due date is 2026-05-15"
    actual = "Due date is 2026/05/15"

    score, performed = get_date_score(expected, actual)
    assert performed is True
    assert score > 0.0


def test_status_score_variations():
    """Test status score with various status values."""
    statuses = ["Paid", "Pending", "Overdue", "Active", "Inactive"]

    for status in statuses:
        expected = f"Your status is '{status}'"
        actual = f"Your status is '{status}'"

        score, performed = get_status_score(expected, actual)
        assert performed is True
        assert score == pytest.approx(1.0)


def test_billing_cycle_variations():
    """Test billing cycle score with various cycle types."""
    cycles = ["Monthly", "Quarterly", "Annual", "Bi-monthly", "Weekly"]

    for cycle in cycles:
        expected = f"Your billing cycle is '{cycle}'"
        actual = f"Your billing cycle is '{cycle}'"

        score, performed = get_billing_cycle_score(expected, actual)
        assert performed is True
        assert score == pytest.approx(1.0)
