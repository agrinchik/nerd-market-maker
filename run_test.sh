#!/usr/bin/env bash

if [ -d "/anaconda3/" ]; then
    source /anaconda3/etc/profile.d/conda.sh
elif [ -d "~/anaconda3/" ]; then
    source ~/anaconda3/etc/profile.d/conda.sh
fi

conda activate nerd-market-maker

echo Executing NerdMarketMaker in BitMex TESTNET ...

cp ./settings_test.py ./settings.py

./marketmaker

