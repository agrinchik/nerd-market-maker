#! /bin/bash

ENV=$1
BOTID=$2
NUMBER_OF_BOTS=$3
ENV_UPPERCASE=$(echo "${ENV}" | tr '[:lower:]' '[:upper:]')


if [[ "$#" -ne 3 ]]; then
    echo "Usage: run_bot.sh <ENV> <BOTID> <NUMBER_OF_BOTS>"
    exit 0
fi

if [ -d "/anaconda3" ]; then
    source /anaconda3/etc/profile.d/conda.sh
elif [ -d "/home/alex/anaconda3" ]; then
    source /home/alex/anaconda3/etc/profile.d/conda.sh
elif [ -d "/Users/alex/anaconda3" ]; then
    source /Users/alex/anaconda3/etc/profile.d/conda.sh
fi
conda activate nerd-market-maker

while true
    if [[ "live" == "${ENV}" ]]; then
       env_param="--live"
    else
       env_param=""
    fi

    echo Launching a NerdMarketMaker bot instance in ${ENV_UPPERCASE}: BotID=${BOTID}

    do python marketmaker.py ${env_param} --botid ${BOTID} --number_of_bots ${NUMBER_OF_BOTS}

    st=$?
    if [ "$st" == "99" ] || [ "$st" == "15" ]; then
        echo "NerdMarketMaker bot instance (${BOTID}) has finished with status code=${st} and the bash script will be terminated!"
        exit 0
    else
        echo "NerdMarketMaker bot instance (${BOTID}) has finished and will be restarted: status code=${st}"
        sleep 5
    fi
done