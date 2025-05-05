# read from dataset.jsonl, example of row:{"conversation": "User: I need help with a charge on my invoice.\nBillingAgent: Sure, I can assist you with that. Can you please provide me with the details of the charge?\nUser: It was an extra fee I wasn't expecting.\n", "target_agent": "BillingAgent", "turns": 1, "temperature": 0.7, "index_batch": 0, "total_batch": 42, "special_case": null, "model": "openai/gpt-4o-mini", "agent_distribution": "BillingAgent:30%-PolicyAgent:20%-ClaimsAgent:25%-EscalationAgent:15%-ChattyAgent:10%", "special_case_distribution": "none:50%-edge_case:10%-cross_domain:10%-language_switch:10%-short_query:5%-complex_query:5%-small_talk:5%-angry_customer:2%-technical_error:2%"}
import json
from dataclasses import dataclass
from pathlib import Path

import dspy

from agents.triage.models import TargetAgent


@dataclass
class DatasetRow:
    conversation: str
    target_agent: TargetAgent
    turns: int
    temperature: float
    index_batch: int
    total_batch: int
    special_case: str
    model: str
    agent_distribution: str
    special_case_distribution: str

    def __post_init__(self):
        self.conversation = self.conversation.strip()
        self.target_agent = self.target_agent.strip()
        self.special_case = self.special_case.strip() if self.special_case else None
        self.agent_distribution = self.agent_distribution.strip()
        self.special_case_distribution = self.special_case_distribution.strip()


def load_dataset(file_path: Path):
    dataset = []
    with open(file_path, 'r') as file:
        for line in file:
            data = json.loads(line)
            if data.get("target_agent") is None:
                continue
            data["target_agent"] = translate_agent_str_to_enum(data["target_agent"])
            dataset.append(DatasetRow(**data))
    return dataset

def translate_agent_str_to_enum(agent_str: str) -> TargetAgent:
    if agent_str == "BillingAgent":
        return TargetAgent.BillingAgent
    elif agent_str == "PolicyAgent":
        return TargetAgent.PolicyAgent
    elif agent_str == "ClaimsAgent":
        return TargetAgent.ClaimsAgent
    elif agent_str == "EscalationAgent":
        return TargetAgent.EscalationAgent
    elif agent_str == "ChattyAgent":
        return TargetAgent.ChattyAgent
    else:
        raise ValueError(f"Unknown agent string: {agent_str}")


def load_dataset_triage_testing():
    return load_dataset(Path(__file__).resolve().parent / "triage-testing.jsonl")

def load_dataset_triage_training():
    return load_dataset(Path(__file__).resolve().parent / "triage-training.jsonl")

def as_dspy_examples(dataset: list[DatasetRow]):
    examples = []
    target_agent_map = {
        "BillingAgent": TargetAgent.BillingAgent,
        "PolicyAgent": TargetAgent.PolicyAgent,
        "ClaimsAgent": TargetAgent.ClaimsAgent,
        "EscalationAgent": TargetAgent.EscalationAgent,
        "ChattyAgent": TargetAgent.ChattyAgent,
    }
    for row in dataset:
        examples.append(dspy.Example(
            chat_history=row.conversation,
            target_agent=target_agent_map[row.target_agent],
        ).with_inputs("chat_history"))
    return examples


if __name__ == "__main__":
    for r in as_dspy_examples(load_dataset_triage_testing()[0:10]):
        print(r)
