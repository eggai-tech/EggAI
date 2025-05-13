from unittest.mock import AsyncMock

import pytest
from dotenv import load_dotenv

from eggai import Channel

from ..src.agents.triage import handle_user_message
from ..datasets.loader import load_dataset



@pytest.mark.asyncio
async def test_triage_agent(monkeypatch):
    load_dotenv()

    dataset = load_dataset("triage-testing")

    total = len(dataset)
    success = 0

    for entry in dataset:
        conversation = entry["conversation"]
        expected_target = entry["target"]
        test_event = {
            "type": "user_message",
            "payload": {"chat_messages": conversation},
        }
        mock_publish = AsyncMock()
        monkeypatch.setattr(Channel, "publish", mock_publish)
        await handle_user_message(test_event)
        args, kwargs = mock_publish.call_args_list[0]
        actual_target = args[0].get("target")
        if actual_target == expected_target:
            success += 1

    success_percentage = (success / total) * 100
    assert (success_percentage > 90), f"Success rate {success_percentage:.2f}% is not greater than 90%."
