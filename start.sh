#!/bin/bash
cd /mnt/c/Users/TEU_USER/Desktop
source botenv/bin/activate

while true; do
  python bot.py
  echo "Bot crashed. Restarting..."
  sleep 5
done
