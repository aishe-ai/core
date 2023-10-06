# 
FROM python:3.11.3

# https://www.sqlite.org/2023/sqlite-tools-linux-x86-3430100.zip
ARG SQLLITE3_NAME=sqlite-tools-linux-x86-3430100
ARG SQLLITE3_ZIP=$SQLLITE3_NAME.zip
# change year in link if needed!
ARG SQLITE3_DOWNLOAD_LINK=https://www.sqlite.org/2023/$SQLLITE3_ZIP

# 
WORKDIR /code/app

# Set environment variables for production
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install wget and download SQLite3 precompiled binaries
RUN apt-get update && \
    wget $SQLITE3_DOWNLOAD_LINK && \
    unzip $SQLLITE3_ZIP && \
    cp $SQLLITE3_NAME/sqlite3 /usr/local/bin/ && \
    rm -rf $SQLLITE3_NAME* 

# 
COPY ./requirements.txt /code/requirements.txt

# 
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# 
COPY . /code/app

# 
CMD uvicorn app:app --proxy-headers --host 0.0.0.0 --port 80 --workers $(nproc)