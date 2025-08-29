#!/bin/bash
echo "Connect to http://localhost:8000"
cd src/ && python3 -m http.server 8000
