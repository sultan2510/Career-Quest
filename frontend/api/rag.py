"""Vercel serverless function that wraps the CareerQuest FastAPI app.

For local Docker Compose development the frontend proxies to the standalone
FastAPI container on port 8000. On Vercel this API route is used instead so
the entire stack deploys as a single serverless project.
"""

import os

os.environ.setdefault("VERCEL", "1")

from main import app

# Reuse the already-built FastAPI app object; Vercel mounts it as a
# serverless function under /api/*.
app