#! /usr/bin/env zsh

ENV=$1
EXCHANGE=$2
ROBOTID=$3
NUMBER_OF_ROBOTS=$4
ENV_UPPERCASE=$(echo "${ENV}" | tr '[:lower:]' '[:upper:]')


if [[ "$#" -ne 4 ]]; then
    echo "Usage: run_robot.sh <ENV> <EXCHANGE> <ROBOTID> <NUMBER_OF_ROBOTS>"
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
    echo Launching a NerdMarketMakerBot instance in ${ENV_UPPERCASE}: BotID=${ROBOTID}

    do python -m market_maker.mm_robot -e ${ENV} --exchange ${EXCHANGE} --robotid ${ROBOTID} --number_of_robots ${NUMBER_OF_ROBOTS}
    st=$?
    if [[ "$st" == "99"  ||  "$st" == "15" ]]; then
        echo "NerdMarketMakerRobot instance (${ROBOTID}) has finished with status code=${st} and the script will be terminated!"
        exit 0
    else
        echo "NerdMarketMakerRobot instance (${ROBOTID}) has finished and will be restarted: status code=${st}"
        sleep 5
    fi
done