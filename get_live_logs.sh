#! /usr/bin/env zsh

rsync -v -a   --include='*nerd_supervisor_log_out.txt' --exclude='*' -e ssh alex@159.69.10.75:/home/alex/nerd-market-maker/logs/live/ ./logs/live/