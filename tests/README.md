# RAG Evaluation Test Suite

This directory contains the test dataset and LLM-as-Judge evaluation for the
Precision Agriculture RAG system.

## Files

- `irrigation_qa_dataset.json` - 50 irrigation engineering Q&A pairs
- `evaluate_rag.py` - LLM-as-Judge evaluation script

## LLM-as-Judge Methodology

Uses five specialized LLM judges:

| Judge | Description |
|-------|-------------|
| Faithfulness | Are claims grounded in context? |
| Answer Relevancy | Does the answer address the question? |
| Context Relevancy | Is retrieved context useful? |
| Agricultural Accuracy | Is the answer domain-specific and correct? |
| Safety | Is advice safe to follow? |

## Running Evaluation

```bash
python tests/evaluate_rag.py --num 3
python tests/evaluate_rag.py
python tests/evaluate_rag.py --num 10 --save
```

## DeepEval Integration

Install DeepEval and Ragas for additional metrics:

```bash
pip install deepeval ragas
```

## Output Format

```json
{
  "summary": {
    "pass_rate": 0.85,
    "scores": {
      "faithfulness": 4.2,
      "precision": 4.0,
      "safety": 4.5
    },
    "concept_coverage": 0.78
  },
  "results": []
}
```
