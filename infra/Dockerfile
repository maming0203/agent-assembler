
FROM python:3.10-slim

WORKDIR /app

# Install deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ /app/src/
COPY examples/ /app/examples/
COPY pyproject.toml .
COPY README.md .
COPY LICENSE .

# Install local package
RUN pip install -e .

# Expose Streamlit port
EXPOSE 8501

# Command
CMD ["streamlit", "run", "examples/web_dashboard.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
