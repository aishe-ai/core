# 
FROM python:3.11.3

# 
WORKDIR /code/app

# Set environment variables for production
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install SQLite3 from apt
RUN apt-get update && apt-get install -y sqlite3 && apt-get clean

# 
COPY ./requirements.txt /code/requirements.txt

# 
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# 
COPY . /code/app

# 
CMD uvicorn app:app --proxy-headers --host 0.0.0.0 --port 80 --workers $(nproc)

