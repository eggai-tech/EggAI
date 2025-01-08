import json
import os
import random
from unittest.mock import AsyncMock
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
import pytest
from dotenv import load_dotenv

from eggai import Channel
from examples.example_08_dspy.src.triage import handle_user_message, AGENT_REGISTRY


def parse_conversation(conversation):
    messages = []
    lines = conversation.strip().split("\n")
    for line in lines:
        if line.startswith("User:"):
            content = line[len("User:") :].strip()
            messages.append({"role": "user", "content": content})
        else:
            try:
                agent_name, content = line.split(":", 1)
                agent_name = agent_name.strip()
                content = content.strip()
                messages.append(
                    {"role": "assistant", "content": content, "agent": agent_name}
                )
            except ValueError:
                continue
    return messages


@pytest.mark.asyncio
async def test_not_optimized_agent(monkeypatch):
    load_dotenv()

    dataset_path = os.path.join(
        os.path.dirname(__file__), "..", "datasets", "triage-training.json"
    )
    with open(dataset_path, "r") as f:
        dataset = json.load(f)

    total = len(dataset)
    success = 0
    failure = 0
    test_results = []

    for entry in dataset:
        conversation = entry["conversation"]
        expected_target = entry["target"]
        test_id = entry.get("id", "N/A")

        chat_messages = parse_conversation(conversation)

        test_event = {
            "type": "user_message",
            "payload": {"chat_messages": chat_messages},
        }

        mock_publish = AsyncMock()
        monkeypatch.setattr(Channel, "publish", mock_publish)
        await handle_user_message(test_event)

        args, kwargs = mock_publish.call_args_list[0]
        message_type = args[0].get("type", "agent_message")
        meta = args[0].get("meta")
        confidence = meta["confidence"]
        reasoning = meta["reasoning"]

        if message_type == "agent_message":
            actual_target = "TriageAgent"
        else:
            actual_target = [
                key
                for key, value in AGENT_REGISTRY.items()
                if value["message_type"] == message_type
            ][0]

        if actual_target == expected_target:
            status = "PASS"
            success += 1
            print(f"Test Case #{test_id}: PASS")
        else:
            status = "FAIL"
            failure += 1
            print(
                f"Test Case #{test_id}: FAIL (Expected: {expected_target}, Got: {actual_target})"
            )

        test_results.append(
            {
                "test_id": test_id,
                "conversation": conversation,
                "expected_target": expected_target,
                "actual_target": actual_target,
                "status": status,
                "confidence": confidence,
                "reasoning": reasoning,
            }
        )

    success_percentage = (success / total) * 100
    print(
        f"\nTotal: {total}, Success: {success}, Failure: {failure}, Success Rate: {success_percentage:.2f}%"
    )

    # Prepare summary for the report
    summary = {
        "total": total,
        "success": success,
        "failure": failure,
        "success_percentage": f"{success_percentage:.2f}",
    }

    # Generate the HTML report
    generate_html_report(test_results, summary)

    # Assert if success percentage is greater than 50%
    assert (
        success_percentage > 50
    ), f"Success rate {success_percentage:.2f}% is not greater than 50%."


