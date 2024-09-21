FROM python:3.9-slim

# Install necessary dependencies
RUN apt-get update && \
    apt-get install -y chromium-driver && \
    apt-get install -y wget gnupg unzip && \
    rm -rf /var/lib/apt/lists/*

# Install Python libraries
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the code into the container
WORKDIR /usr/src/app
COPY bus_schedule_service.py .
COPY run.sh .

# Make the run.sh script executable
RUN chmod +x run.sh

# Run the script when the container launches
CMD [ "/usr/src/app/run.sh" ]
