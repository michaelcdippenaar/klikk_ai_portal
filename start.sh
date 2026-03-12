#!/bin/bash
# Launch the Klikk Planning Agent Streamlit UI
# Run from: /home/mc/tm1_models/klikk_group_planning_v3/agent/
# Access at: http://192.168.1.194:8501

set -e
cd "$(dirname "$0")"

if [ ! -f ".env" ]; then
    echo "ERROR: agent/.env not found."
    echo "Copy .env.template to .env and fill in your API keys and passwords."
    exit 1
fi

# Activate the Python 3.12 virtual environment
source .venv/bin/activate

echo "Starting Klikk Planning Agent on http://192.168.1.194:8501 ..."
streamlit run ui/app.py \
    --server.address 0.0.0.0 \
    --server.port 8501 \
    --server.headless true \
    --browser.gatherUsageStats false
