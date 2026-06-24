# Use a lightweight official Python runtime
FROM python:3.11-slim

WORKDIR /app

# Install package dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app.py .

# Inform Docker that the container listens on port 5000
EXPOSE 5002

# Execute the application
CMD ["python", "app.py"]
