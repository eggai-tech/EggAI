# Custom Classifiers Model Training Guide

This guide explains how to train custom classifiers for the Triage Agent to improve response latency and reduce costs.

## Data Analysis

The training and test data has been generated via data generation scripts. You can explore the data using the Jupyter notebook:

```bash
make start-eda-notebook
```

This opens a notebook at http://localhost:8888 with exploratory data analysis including:

### Training Data Visualization

<img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/train_tsne.png" width="600"/>

### Test Data Visualization

<img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/test_tsne.png" width="600"/>

The t-SNE projections show clear clustering of messages by intent, indicating that a simple classifier should perform well.

## Baseline Model (Few-Shot Logistic Regression)

The baseline model uses:

- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)
- **Classifier**: Logistic regression trained on message embeddings
- **Few-shot learning**: Can train with limited examples per class

### Training

1. Configure environment variables in `.env`:

```bash
FEWSHOT_N_EXAMPLES=100  # Number of examples per class
AWS_ACCESS_KEY_ID=user
AWS_SECRET_ACCESS_KEY=password
MLFLOW_TRACKING_URI=http://localhost:5001
MLFLOW_S3_ENDPOINT_URL=http://localhost:9000
```

2. Train the model:

```bash
make train-triage-classifier-v3
```

3. Test the model:

```bash
make test-triage-classifier-v3
```

### Available Models

1. **Baseline Few-Shot Classifier (v3)**

   ```bash
   make train-triage-classifier-v3
   ```

   - Uses few-shot learning with examples
   - Good baseline performance
   - Requires training data

2. **Attention-Based Classifier (v5)**

   ```bash
   make train-triage-classifier-v5
   ```

   - Advanced neural architecture
   - Best performance on complex queries
   - Requires GPU for optimal training

### Monitoring Training Progress

View training metrics and model performance:

- MLflow UI: <http://localhost:5001>
- Experiments are organized by model version
- Compare runs across different hyperparameters

### Evaluating Models

```bash
make test-triage-classifier-v3  # Test baseline model
make test-triage-classifier-v5  # Test attention model
```

### Results

Compare models with different training set sizes in MLflow:

<img src="https://raw.githubusercontent.com/eggai-tech/EggAI/refs/heads/main/docs/docs/assets/triage-custom-classifier-training.png" width="1600"/>

The results show that even with just 100 examples per class, the model achieves good performance.

## Attention-Based Classifier

The attention-based classifier addresses the "intent change" problem where users switch topics mid-conversation.

### How it Works

- Computes embeddings for each message in the conversation
- Uses attention pooling to focus on relevant messages
- Provides interpretable attention weights

### Benefits

- Handles topic changes within conversations
- Provides explainable predictions via attention weights
- Better performance on complex multi-turn conversations

## Monitoring Results

View all training runs and compare models at http://localhost:5001 (MLflow UI).

Key metrics to track:

- Accuracy per class
- Overall F1 score
- Inference latency
- Model size
