from fastapi import FastAPI
from backend.app.main import app

print("Routes registered:")
for route in app.routes:
    print(f"{route.path} [{route.methods}]")
