#! /bin/bash

rsync -v -a   --include='mm_*_log_out.txt' --exclude='*' -e ssh alex@159.69.10.75:/home/alex/nerd-market-maker/ ./logs/