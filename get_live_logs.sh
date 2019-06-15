#! /bin/bash

rsync -v -a   --include='ttt_mm' --exclude='*' -e ssh alex@159.69.10.75:/home/alex/nerd-market-maker/ ./logs/