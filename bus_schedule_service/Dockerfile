FROM python:3.9-slim

# Install necessary dependencies in one RUN command
RUN apt-get update && \
    apt-get install -y \
        chromium-driver \
        wget \
        gnupg \
        unzip \
        jq && \
    rm -rf /var/lib/apt/lists/*

# Install Python libraries
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Set the working directory
WORKDIR /usr/src/app

# Copy the application code into the container
COPY bus_schedule_service.py .
COPY run.sh .

# Make run.sh executable
RUN chmod +x run.sh

# Run the application when the container starts
CMD [ "/usr/src/app/run.sh" ]
