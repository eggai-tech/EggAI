import mlflow


def find_artifact(artifact_name: str):
    all_runs = mlflow.search_runs()
    for run in all_runs.itertuples():
        artifacts = mlflow.artifacts.list_artifacts(run.artifact_uri)
        for artifact in artifacts:
            if artifact_name in artifact.path:
                return run.artifact_uri + '/' + artifact_name

    raise FileNotFoundError(f"Artifact {artifact_name} not found in any run.")