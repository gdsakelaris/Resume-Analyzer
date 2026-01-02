#!/bin/bash

echo "=== Docker Compose Services Status ==="
docker-compose ps

echo -e "\n=== Redis Container Health ==="
docker-compose logs redis --tail 20

echo -e "\n=== Testing Redis Connection from API Container ==="
docker-compose exec api sh -c "python -c 'import redis; r = redis.Redis(host=\"redis\", port=6379, db=0); print(\"Redis ping:\", r.ping())'" 2>&1

echo -e "\n=== Testing Redis Connection from Worker Container ==="
docker-compose exec worker sh -c "python -c 'import redis; r = redis.Redis(host=\"redis\", port=6379, db=0); print(\"Redis ping:\", r.ping())'" 2>&1

echo -e "\n=== Network Connectivity ==="
docker-compose exec api ping -c 2 redis 2>&1

echo -e "\n=== Environment Variables in API ==="
docker-compose exec api sh -c "env | grep -i redis"

echo -e "\n=== Recent API Errors ==="
docker-compose logs api --tail 50 | grep -i "error\|redis\|connection"
