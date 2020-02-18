#! /usr/bin/env zsh

ENV=$1
EXCHANGE=$2
BOTID=$3
NUMBER_OF_BOTS=$4
ENV_UPPERCASE=$(echo "${ENV}" | tr '[:lower:]' '[:upper:]')


if [[ "$#" -ne 4 ]]; then
    echo "Usage: run_bot.sh <ENV> <EXCHANGE> <BOTID> <NUMBER_OF_BOTS>"
    exit 0
fi

if [[ -d "/opt/anaconda3" ]]; then
    source /opt/anaconda3/etc/profile.d/conda.sh
elif [[ -d "/home/alex/anaconda3" ]]; then
    source /home/alex/anaconda3/etc/profile.d/conda.sh
elif [[ -d "/Users/alex/anaconda3" ]]; then
    source /Users/alex/anaconda3/etc/profile.d/conda.sh
fi
conda activate nerd-market-maker

while true
    echo Launching a NerdMarketMakerBot instance in ${ENV_UPPERCASE}: BotID=${BOTID}

    do python -m market_maker.mm_bot -e ${ENV} --exchange ${EXCHANGE} --botid ${BOTID} --number_of_bots ${NUMBER_OF_BOTS}
    st=$?
    if [[ "$st" == "99"  ||  "$st" == "15" ]]; then
        echo "NerdMarketMakerBot instance (${BOTID}) has finished with status code=${st} and the bash script will be terminated!"
        exit 0
    else
        echo "NerdMarketMakerBot instance (${BOTID}) has finished and will be restarted: status code=${st}"
        sleep 5
    fi
done