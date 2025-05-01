from pathlib import Path

import dotenv
from mlflow import MlflowClient

dotenv.load_dotenv()


def find_model(model_name: str, version: str):
    base = Path(__file__).resolve().parent
    cache_path = base.parents[2] / ".cache"
    cache_path.mkdir(parents=True, exist_ok=True)

    pickle_path = cache_path / model_name / version / "model" / "model.pkl"
    if pickle_path.exists():
        return pickle_path

    client = MlflowClient()
    mv = client.get_model_version(name=model_name, version=version)
    run_id = mv.run_id
    artifact_path = "model"

    dest = cache_path / model_name / version
    dest.mkdir(parents=True, exist_ok=True)
    client.download_artifacts(run_id, artifact_path, dst_path=str(dest))

    return pickle_path


if __name__ == "__main__":
    p = find_model("fewshot_classifier_n_200", version="1")
    print(p)
