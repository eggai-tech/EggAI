import asyncio
from typing import Optional

import litellm
from tqdm import tqdm

from triage_agent_dataset.config import AppConfig
from triage_agent_dataset.constants import (
    SPECIAL_CASE_ADDITIONAL_INSTRUCTIONS,
    SYSTEM_PROMPT,
)
from triage_agent_dataset.models import Agents, ConversationExample, SpecialCaseType

config = AppConfig()


def deserialize_response(response: str):
    """
    Deserialize a conversation string into a dictionary.
    """
    lines = response.strip().split("\n")
    conversation = ""
    target_agent = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#conversation#"):
            continue
        elif line.startswith("#target_agent#"):
            target_agent = line[len("#target_agent#") :].strip()
        else:
            parts = line.split(":", 1)
            if len(parts) != 2:
                continue
            role, content = parts[0].strip(), parts[1].strip()
            conversation += f"{role}: {content}\n"
    return {"conversation": conversation, "target_agent": target_agent}


async def generate_examples(
    target_agent: Agents,
    num_examples: int,
    temperature: float,
    turns: int,
    special_case: Optional[SpecialCaseType] = None,
    progress: Optional[tqdm] = None,
):
    """
    Asynchronously generate a batch of examples for the given target agent and combination.
    Updates the provided tqdm progress bar after each example.
    """

    def add_metadata(example, index_batch):
        return ConversationExample(
            conversation=example["conversation"],
            target_agent=example["target_agent"],
            turns=turns,
            temperature=temperature,
            index_batch=index_batch,
            total_batch=num_examples,
            special_case=special_case.value if special_case else None,
            model=config.MODEL,
        )

    local_batch = []
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
            + (
                SPECIAL_CASE_ADDITIONAL_INSTRUCTIONS.get(special_case.value, "")
                if special_case
                else ""
            ),
        },
        {
            "role": "user",
            "content": f"Generate an example for the dataset. The #target_agent# should be {target_agent.value}. The number of messages in the conversation should be {turns}. Remember the first and the latest turn are from the user.",
        },
    ]

    for idx in range(num_examples):
        if idx == 0:
            response = await litellm.acompletion(
                model=config.MODEL,
                messages=messages,
                temperature=temperature,
            )
            parsed = deserialize_response(response.choices[0].message.content)
            local_batch.append(add_metadata(parsed, idx))
            messages.append(
                {
                    "role": "assistant",
                    "content": response.choices[0].message.content,
                }
            )
        else:
            messages.append(
                {
                    "role": "user",
                    "content": f"Generate another example for the dataset. The #target_agent# should be {target_agent.value}. The number of messages in the conversation should be {turns}. Remember the first and the latest turn are from the user.",
                }
            )
            response = await litellm.acompletion(
                model=config.MODEL,
                messages=messages,
                temperature=temperature,
            )
            parsed = deserialize_response(response.choices[0].message.content)
            local_batch.append(add_metadata(parsed, idx))
            messages.append(
                {
                    "role": "assistant",
                    "content": response.choices[0].message.content,
                }
            )
        if progress is not None:
            progress.update(1)
    return local_batch


async def generate_conversation_per_agent(
    agent: Agents, turns: list, temperatures: list, progress: tqdm
) -> list:
    tasks = []
    agent_frac = config.AGENT_DISTRIBUTION.get(agent.value, 0)
    agent_target = max(round(config.TOTAL_TARGET * agent_frac), 1)
    num_combinations = len(turns) * len(temperatures)
    ideal_per_combo = agent_target / num_combinations

    for turn in turns:
        for temperature in temperatures:
            for special_key, frac in config.SPECIAL_CASE_DISTRIBUTION.items():
                count = round(ideal_per_combo * frac)
                count = max(count, 1)
                special = (
                    None if special_key == "none" else SpecialCaseType(special_key)
                )

                tasks.append(
                    generate_examples(
                        agent,
                        count,
                        temperature,
                        turn,
                        special_case=special,
                        progress=progress,
                    )
                )
    results = await asyncio.gather(*tasks)
    return [example for sublist in results for example in sublist]
