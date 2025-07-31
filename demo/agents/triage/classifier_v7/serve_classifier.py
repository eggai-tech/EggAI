import logging
import os

import mlflow
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoTokenizer

from agents.triage.baseline_model.utils import setup_logging
from agents.triage.classifier_v7.classifier_v7 import FinetunedClassifier
from agents.triage.classifier_v7.device_utils import get_device_config
from agents.triage.classifier_v7.gemma3_seq_cls import (
    Gemma3TextForSequenceClassification,
)
from agents.triage.data_sets.loader import ID2LABEL

load_dotenv()

logger = logging.getLogger(__name__)
setup_logging()
device_map, dtype = get_device_config()

# load run_id from MLFLOW_RUN_ID
run_id = os.getenv("MLFLOW_RUN_ID")

logger.info(f"Downloading model artifacts from MLflow run: {run_id}")
model_path = mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path="model")

logger.info(f"Loading model from: {model_path}")

model = Gemma3TextForSequenceClassification.from_pretrained(
    model_path,
    num_labels=len(ID2LABEL),
    torch_dtype=dtype,
    device_map=device_map,
    attn_implementation="eager"
)
tokenizer = AutoTokenizer.from_pretrained(model_path)
model.eval()

# create FinetunedClassifier
classifier = FinetunedClassifier(model=model, tokenizer=tokenizer)

app = FastAPI(title="Fine-tuned Model Server")

class PredictRequest(BaseModel):
    inputs: list[str]


@app.post("/invocations")
async def predict(request: PredictRequest):
    return classifier.classify(request.inputs[0])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
