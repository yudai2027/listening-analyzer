#!/bin/bash
# Deploy script: copies add-on files to Anki's add-on folder after git push.
#
# Usage:
#   1. Edit ADDON_DIR below to match your Anki add-on folder path
#   2. Run: ./deploy.sh
#   Or set up as a git post-push hook (see below)
#
# To auto-run on every push, create .git/hooks/post-push:
#   #!/bin/bash
#   ./deploy.sh

# --- EDIT THIS: Your Anki add-on folder path ---
# macOS:   ~/Library/Application Support/Anki2/User 1/addons21/<addon_folder>
# Windows: %APPDATA%/Anki2/User 1/addons21/<addon_folder>
# Linux:   ~/.local/share/Anki2/User 1/addons21/<addon_folder>
ADDON_DIR=""

if [ -z "$ADDON_DIR" ]; then
    echo "Error: ADDON_DIR is not set. Edit deploy.sh and set your Anki add-on folder path."
    exit 1
fi

if [ ! -d "$ADDON_DIR" ]; then
    echo "Error: Directory not found: $ADDON_DIR"
    echo "Make sure the path is correct and Anki has been run at least once."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cp "$SCRIPT_DIR/__init__.py" "$ADDON_DIR/__init__.py"
cp "$SCRIPT_DIR/config.json" "$ADDON_DIR/config.json" 2>/dev/null

echo "Deployed to $ADDON_DIR"
echo "Restart Anki to apply changes."
