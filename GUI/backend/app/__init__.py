import os
import sys

PLANTOR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
print(f"Adding {PLANTOR_PATH} to sys.path")
sys.path.append(PLANTOR_PATH)

PUBLIC_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "..",
    "frontend",
    "public_generated",
)
os.makedirs(PUBLIC_PATH, exist_ok=True)
