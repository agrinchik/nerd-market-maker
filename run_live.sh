#!/usr/bin/env bash

if [ -d "/anaconda3" ]; then
    source /anaconda3/etc/profile.d/conda.sh
elif [ -d "/home/alex/anaconda3" ]; then
    source /home/alex/anaconda3/etc/profile.d/conda.sh
elif [ -d "/Users/alex/anaconda3" ]; then
    source /Users/alex/anaconda3/etc/profile.d/conda.sh
fi

conda activate nerd-market-maker

echo Executing NerdMarketMaker in LIVE environment ...

while true
    do ./marketmaker --live
    st=$?
    echo $st
    if [ "$st" -eq "99" ]; then
        echo "NerdMarketMaker has finished with status code=99 and the bash script will be terminated!"
        break
    else
        echo "NerdMarketMaker has finished and will be restarted: status code="$st
        sleep 5
    fi
done
