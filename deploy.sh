#!/bin/bash
# Deploy script: copies add-on files to Anki's add-on folder.
#
# Setup:
#   1. cp .env.example .env
#   2. Edit .env and set ADDON_DIR to your Anki add-on folder path
#   3. Run: ./deploy.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load path from .env (not committed to git)
if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
fi

if [ -z "$ADDON_DIR" ]; then
    echo "Error: ADDON_DIR is not set."
    echo "Run: cp .env.example .env  then edit .env"
    exit 1
fi

if [ ! -d "$ADDON_DIR" ]; then
    echo "Error: Directory not found: $ADDON_DIR"
    exit 1
fi

cp "$SCRIPT_DIR/__init__.py" "$ADDON_DIR/__init__.py"
cp "$SCRIPT_DIR/config.json" "$ADDON_DIR/config.json" 2>/dev/null

echo "Deployed to $ADDON_DIR"
echo "Restart Anki to apply changes."
