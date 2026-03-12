#!/bin/bash

# Read task output from stdin
input=$(cat)

# Extract first line or truncate to reasonable length
message=$(echo "$input" | head -n 1 | cut -c 1-100)

# If empty, use default
if [ -z "$message" ]; then
    message="任务完成"
fi

# Send notification
terminal-notifier \
    -message "$message" \
    -title "Claude Code" \
    -sound Funk \
    -sender com.apple.Terminal \
    -ignoreDnD
