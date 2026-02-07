FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 1. Install system build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 2. Copy metadata first (to cache dependencies)
# We need README.md because your pyproject.toml references it
COPY pyproject.toml README.md ./

# 3. Install dependencies only
# This will fail to 'install' the app (which is fine), but it will download 
# all dependencies listed in your pyproject.toml and cache them.
RUN pip install --no-cache-dir . --dry-run || true

# 4. Now copy the actual source code and the rest of the files
COPY . .

# 5. Final install of the project (this will now find the 'app' folder)
RUN pip install --no-cache-dir .

EXPOSE 8000

# Start FastAPI using the 'app' folder
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]