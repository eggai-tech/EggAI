import argparse
import asyncio
from typing import List, Optional

import dotenv
from tqdm import tqdm

from triage_agent_dataset.config import AppConfig
from triage_agent_dataset.dataset_generator import generate_conversation_per_agent
from triage_agent_dataset.models import Agents


async def generate_dataset(
    output_file: str = "dataset.jsonl", 
    temperatures: Optional[List[float]] = None,
    turns: Optional[List[int]] = None,
    total_target: Optional[int] = None
) -> None:
    """
    Generate a dataset using the specified parameters
    """
    # Initialize default values if not provided
    if temperatures is None:
        temperatures = [0.7, 0.8, 0.9]
    if turns is None:
        turns = [1, 3, 5]
    
    dataset = []
    config = AppConfig()
    
    # Override config values if provided
    if total_target is not None:
        config.TOTAL_TARGET = total_target

    # Calculate total examples for progress tracking
    total_examples = 0
    for agent in Agents:
        agent_frac = config.AGENT_DISTRIBUTION.get(agent.value, 0)
        agent_target = max(round(config.TOTAL_TARGET * agent_frac), 1)
        num_combinations = len(turns) * len(temperatures)
        ideal_per_combo = agent_target / num_combinations
        for _ in range(len(turns) * len(temperatures)):
            for frac in config.SPECIAL_CASE_DISTRIBUTION.values():
                count = round(ideal_per_combo * frac)
                total_examples += max(count, 1)

    progress = tqdm(total=total_examples, desc="Generating Dataset", position=0)

    agent_tasks = [
        generate_conversation_per_agent(agent, turns, temperatures, progress)
        for agent in Agents
    ]
    results = await asyncio.gather(*agent_tasks)
    progress.close()

    for agent_result in results:
        dataset.extend(agent_result)

    print(f"Generated total examples: {len(dataset)}")

    with open(output_file, "w") as f:
        for example in dataset:
            f.write(example.model_dump_json() + "\n")


def main():
    """
    Main entry point for the triage-generate command
    """
    # Load environment variables
    dotenv.load_dotenv()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Generate a triage agent dataset")
    parser.add_argument(
        "--output", "-o", 
        type=str, 
        default="dataset.jsonl", 
        help="Output file path (default: dataset.jsonl)"
    )
    parser.add_argument(
        "--temperatures", "-t", 
        type=float, 
        nargs="+", 
        help="List of temperatures to use (default: 0.7 0.8 0.9)"
    )
    parser.add_argument(
        "--turns", "-u", 
        type=int, 
        nargs="+", 
        help="List of turns to use (default: 1 3 5)"
    )
    parser.add_argument(
        "--total", "-n", 
        type=int, 
        help="Total number of examples to generate (overrides config value)"
    )
    
    args = parser.parse_args()
    
    # Run the dataset generation
    asyncio.run(generate_dataset(
        output_file=args.output,
        temperatures=args.temperatures,
        turns=args.turns,
        total_target=args.total
    ))


if __name__ == "__main__":
    main()
