from typing import Any

from libraries.logger import get_console_logger

logger = get_console_logger("libraries.patches")


def patch_usage_tracker():
    # FIXME: Patch the UsageTracker to handle nested dicts in usage entries
    def _merge_usage_entries(self, entry1, entry2) -> dict[str, dict[str, Any]]:
        # If one side is empty or None, just clone the other
        if not entry1:
            return dict(entry2 or {})
        if not entry2:
            return dict(entry1 or {})

        # Start with a shallow copy of entry2
        result = dict(entry2)

        for key, val1 in entry1.items():
            val2 = result.get(key)

            # If either side is a dict, merge them recursively (treat None as {})
            if isinstance(val1, dict) or isinstance(val2, dict):
                sub1 = val1 if isinstance(val1, dict) else {}
                sub2 = val2 if isinstance(val2, dict) else {}
                result[key] = self._merge_usage_entries(sub1, sub2)

            else:
                # Treat None or missing as zero, then sum
                num1 = val1 or 0
                num2 = val2 or 0
                result[key] = num1 + num2

        return result

    # Apply the patch
    from dspy.utils.usage_tracker import UsageTracker
    UsageTracker._merge_usage_entries = _merge_usage_entries
    logger.info("DSPY UsageTracker patched successfully")