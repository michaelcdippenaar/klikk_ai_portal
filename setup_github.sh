#!/bin/bash
# Run this once to create the GitHub repo and push code
# It will open a browser for GitHub authentication
set -e
cd /home/mc/apps/klikk_ai_portal

# Install latest gh CLI
(type -p wget >/dev/null || (echo 'pass' | sudo -S apt install wget -y))   && echo 'pass' | sudo -S mkdir -p -m 755 /etc/apt/keyrings   && wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null   && echo 'pass' | sudo -S chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg   && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli-stable.list > /dev/null   && echo 'pass' | sudo -S apt update -qq   && echo 'pass' | sudo -S apt install gh -y -qq

# Authenticate with GitHub
gh auth login --hostname github.com --git-protocol ssh --web

# Create the private repo and push
gh repo create michaelcdippenaar/klikk-ai-portal --private --description 'Klikk AI Planning Portal — TM1 Financial Planning Agent' --source . --remote origin --push

echo 'Done! GitHub repo created and code pushed.'
