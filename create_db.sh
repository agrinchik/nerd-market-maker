#! /bin/bash

if [ -d "/anaconda3" ]; then
    source /anaconda3/etc/profile.d/conda.sh
elif [ -d "/home/alex/anaconda3" ]; then
    source /home/alex/anaconda3/etc/profile.d/conda.sh
elif [ -d "/Users/alex/anaconda3" ]; then
    source /Users/alex/anaconda3/etc/profile.d/conda.sh
fi
conda activate nerd-market-maker

echo Creating initial database for NerdMarketMaker application
echo ......
python ./market_maker/db/create_db.py
echo Completed!