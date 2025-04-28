## MLFlow server with pre-trained models
In order to run the MLFlow tracking server together with the artifact server, run the following command:
```bash
docker-compose up
```
See our [MLFLow setup](https://github.com/eggai-tech/hello-mlflow) for more details.

Now populate the MLFlow server with the pre-trained models. You can do this by exporting the necessary environment variables:
```bash
# Set environment variables
export MLFLOW_TRACKING_URI=http://localhost:5000
export MLFLOW_S3_ENDPOINT_URL=http://localhost:9000
export AWS_ACCESS_KEY_ID=user
export AWS_SECRET_ACCESS_KEY=password
```
and then running the following command:
```bash
python upload_checkpoints.py
```
This will upload the [pre-trained models](baseline_checkpoints) to the MLFlow artifact storage and print the artifact URLs to the console.

In order to create the model and load the model weights from the MLFlow artifact storage, use the following:
```python
import mlflow
from triage_classifier.models.fewshot_classifier import FewshotClassifier

downloaded_model_path = mlflow.artifacts.download_artifacts(ARTIFACT_URI)
fewshot_classifier = FewshotClassifier()
fewshot_classifier.load(downloaded_model_path)
```
where `ARTIFACT_URI` is one of the URLs printed by the `upload_checkpoints.py` script.

Make sure that `mlflow` and `boto3` are installed in your environment.

Now you can use the `fewshot_classifier` object to make predictions on the incoming messages.