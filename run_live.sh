#!/usr/bin/env bash

if [ -d "/anaconda3" ]; then
    source /anaconda3/etc/profile.d/conda.sh
elif [ -d "/home/alex/anaconda3" ]; then
    source /home/alex/anaconda3/etc/profile.d/conda.sh
fi

conda activate nerd-market-maker

echo Executing NerdMarketMaker in BitMex LIVE ...

while true
    do ./marketmaker --live
    if [ $? -eq 99 ]; then
        echo "NerdMarketMaker has finished with status code=99 and the bash script will be terminated!"
        break
    else
        echo "NerdMarketMaker has finished and will be restarted: status code="$?
        sleep 10
    fi
done
