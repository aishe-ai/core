FROM python:3.10

# Set working directory
WORKDIR /code/app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install required packages and download, compile
RUN apt-get update && \
    apt-get install -y wget build-essential

# Install tesseract-ocr, poppler-utils, and playwright in a separate layer
RUN apt-get update && \
    apt-get install -y tesseract-ocr poppler-utils && \
    pip install playwright && \
    playwright install

# Copy requirements file
COPY ./requirements.txt /code/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy application code
COPY . /code/app

# Run application
CMD uvicorn app:app --proxy-headers --host 0.0.0.0 --port 8888 --workers $(nproc)
