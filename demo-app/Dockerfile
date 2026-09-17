FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install FlagOps SDK from local source
COPY sdk/python /sdk/python
RUN pip install --no-cache-dir /sdk/python

# Install demo app requirements
COPY demo-app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy demo app source
COPY demo-app /app

EXPOSE 3001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001"]
