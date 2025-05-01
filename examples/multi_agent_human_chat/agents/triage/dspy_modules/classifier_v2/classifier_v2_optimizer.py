from itertools import product
from pathlib import Path
from types import SimpleNamespace

from dspy.evaluate import Evaluate
from dspy.teleprompt import BootstrapFewShotWithRandomSearch
from sklearn.model_selection import train_test_split

from agents.triage.data_sets.loader import (
    as_dspy_examples,
    load_dataset_triage_training,
    load_dataset_triage_testing,
)
from agents.triage.dspy_modules.classifier_v1 import classifier_v1
from libraries.dspy_set_language_model import dspy_set_language_model


# ------------------------------------------------------------------
# Metric: 1 = label matches, 0 = otherwise (sufficient for DSPy’s optimiser)
# ------------------------------------------------------------------
def macro_f1(example, pred, trace=None):
    return float(example.target_agent.lower() == pred.target_agent.lower())


if __name__ == "__main__":
    # ------------------------------------------------------------------
    # Env + LM
    # ------------------------------------------------------------------
    from dotenv import load_dotenv
    load_dotenv()

    lm = dspy_set_language_model(
        SimpleNamespace(
            language_model="openai/gpt-4o-mini",
            cache_enabled=True,
            language_model_api_base=None,
        )
    )

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    full_train = as_dspy_examples(load_dataset_triage_training())   # 1 000
    test_set   = as_dspy_examples(load_dataset_triage_testing())    # 2 400

    train_set, dev_set = train_test_split(
        full_train,
        test_size=0.20,
        stratify=[ex.target_agent for ex in full_train],
        random_state=42,
    )

    # ------------------------------------------------------------------
    # Evaluator (re-used for every candidate prompt)
    # ------------------------------------------------------------------
    evaluator = Evaluate(devset=dev_set, metric=macro_f1, num_threads=8)

    # ------------------------------------------------------------------
    # Tiny hyper-grid search
    # ------------------------------------------------------------------
    SEARCH_SPACE = {
        "max_labeled_demos":      [16, 32],
        "max_bootstrapped_demos": [4, 8],
        "max_rounds":             [6, 10],
    }

    best_program, best_dev = None, -1

    for values in product(*SEARCH_SPACE.values()):
        hp = dict(zip(SEARCH_SPACE.keys(), values))

        tele = BootstrapFewShotWithRandomSearch(
            metric=macro_f1,
            num_candidate_programs=8,      # shuffled-prompt candidates
            max_errors=15,
            **hp,
        )

        prog = tele.compile(classifier_v1, trainset=train_set, valset=dev_set)

        # -------------------------- FIXED EVALUATION -------------------
        score = evaluator(prog)            # average accuracy on dev_set
        # ----------------------------------------------------------------

        if score > best_dev:
            best_program, best_dev, best_hp = prog, score, hp
            print(f"✓ new best {best_dev:.3f} with {best_hp}")

    # ------------------------------------------------------------------
    # Persist the winner
    # ------------------------------------------------------------------
    json_path = Path(__file__).resolve().parent / "optimizations_v2.json"
    best_program.save(str(json_path))
    print(f"Saved best program ({best_dev:.3f} dev accuracy) → {json_path}")
