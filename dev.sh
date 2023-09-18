#!/bin/bash

task_queue=$(python3 - <<END
import config
print(config.task_queue)if hasattr(config, "task_queue") else print()
END
)
if [ "$task_queue" == "kafka" ]; then
    # Initialize DOCKER_COMPOSE variable
    DOCKER_COMPOSE=""

    # Check if Docker is installed
    if command -v docker &> /dev/null; then
        DOCKER_COMPOSE="docker compose"
    else
        # Check if Docker Compose is installed
        if command -v docker-compose &> /dev/null; then
            DOCKER_COMPOSE="docker-compose"
        else
            echo "Error: Neither Docker nor Docker Compose is installed."
            echo "Please install Docker or Docker Compose before continuing."
            exit 1
        fi
    fi

    $DOCKER_COMPOSE -f kafka-docker-compose.yml up -d

    python3 ingest-task-consumer.py >> kafka-task-consumer.log 2>&1 &
fi

export DEV="True"
python3 ./main.py

if [ "$task_queue" == "kafka" ]; then
    $DOCKER_COMPOSE -f kafka-docker-compose.yml down
    pkill -f "ingest-task-consumer.py"
fi
