# RAGAS RAG evaluation pipeline.
#
# Requires a running KB (knowledge_chunks_dev or knowledge_chunks table populated)
# and the RAGAS_DB_URL environment variable set.  Available from Phase 2 onwards.
#
# Usage:
#   uv run --package evaluation python -m evaluation.rag.runner
