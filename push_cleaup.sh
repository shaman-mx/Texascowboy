#!/bin/bash
# push_cleanup.sh - xoá logic push git tự động
rm -f /tmp/id_render_deploy /tmp/known_hosts_render
echo "Remove GIT_SSH_KEY env var from Render dashboard"
echo "Remove deploy key from GitHub repo Settings -> Deploy keys"
echo "Remove git_push.py and any calls in main.py"