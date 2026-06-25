# FAQ Agent — Setup Guide

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Install `pgvector` Python client separately (required for PostgreSQL vector type support):

```bash
pip install pgvector
```

---

## 2. Install spaCy Model

Required by the BM25 tokenizer inside the FAQ pipeline:

```bash
python -m spacy download en_core_web_sm
```

---

## 3. Download MS-Marco Reranker Model

Download the cross-encoder reranker from HuggingFace using Python:

```python
from sentence_transformers import CrossEncoder
CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", cache_folder="D:/AI/Agent/ms-marco-reranker")
```

Or using the HuggingFace CLI:

```bash
pip install huggingface_hub
huggingface-cli download cross-encoder/ms-marco-MiniLM-L-6-v2 --local-dir D:/AI/Agent/ms-marco-reranker
```

Set the path in `.env`:

```env
RERANKER_PATH=D:/AI/Agent/ms-marco-reranker
```

---

## 4. PostgreSQL + pgvector Setup

The `vector` extension and `faq_embeddings` table are created automatically when the scraper runs.
The `chat_history` table is created automatically when the server starts.

---


## 5. Run the Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 80
```
