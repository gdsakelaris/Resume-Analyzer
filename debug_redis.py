#!/usr/bin/env python3
"""Debug Redis connection"""
import sys
sys.path.insert(0, '/app')

from app.core.config import settings
import redis

print("=" * 60)
print("Redis Configuration Debug")
print("=" * 60)
print(f"REDIS_HOST: {settings.REDIS_HOST}")
print(f"REDIS_PORT: {settings.REDIS_PORT}")
print(f"REDIS_DB: {settings.REDIS_DB}")
print(f"REDIS_URL: {settings.REDIS_URL}")
print()

print("Testing Redis connection...")
try:
    r = redis.from_url(settings.REDIS_URL)
    r.ping()
    print("✅ SUCCESS: Redis connection works!")
except Exception as e:
    print(f"❌ FAILED: {e}")
print()

print("Testing Celery app configuration...")
from app.core.celery_app import celery_app
print(f"Celery broker: {celery_app.conf.broker_url}")
print(f"Celery backend: {celery_app.conf.result_backend}")
