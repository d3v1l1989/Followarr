#!/bin/bash

# Ensure we're in the project root
cd "$(dirname "$0")/.."

# Install required packages if they're not already installed
pip3 install -r requirements.txt

# Run the test
python3 tests/test_rookie.py 