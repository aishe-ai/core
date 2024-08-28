FROM python:3.10

# SQLite3 variables
ARG SQLITE3_NAME=sqlite-autoconf-3430100
ARG SQLITE3_TAR=$SQLITE3_NAME.tar.gz
ARG SQLITE3_DOWNLOAD_LINK=https://www.sqlite.org/2023/$SQLITE3_TAR

# Set working directory
WORKDIR /code/app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install required packages and download, compile, and install SQLite3
RUN apt-get update && \
    apt-get install -y wget build-essential
    # && \
    # wget $SQLITE3_DOWNLOAD_LINK && \
    # tar xvf $SQLITE3_TAR && \
    # cd $SQLITE3_NAME && \
    # ./configure && \
    # make && \
    # make install && \
    # cd .. && \
    # rm -rf $SQLITE3_NAME*

# Install tesseract-ocr, poppler-utils, and playwright in a separate layer
RUN apt-get update && \
    apt-get install -y tesseract-ocr poppler-utils && \
    pip install playwright && \
    playwright install

# Copy requirements file
COPY ./requirements.txt /code/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# SQLite version change
# https://stackoverflow.com/questions/62523183/how-to-change-sqlite-version-used-by-python
ENV LD_LIBRARY_PATH="/usr/local/lib"

# Copy application code
COPY . /code/app

# Run application
CMD uvicorn app:app --proxy-headers --host 0.0.0.0 --port 8888 --workers $(nproc)
