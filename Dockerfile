# Use an official Python runtime as the parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container to /app
WORKDIR /app

# Copy the project directory contents into the container at /app
COPY src /app/
COPY pyproject.toml /app/
COPY poetry.lock /app/
COPY .env.sample /app/.env

# Install any needed packages specified
RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-root \
    && rm -rf /root/.cache/pypoetry

# Specify the command to run on container start
CMD ["/app/run.py"]
