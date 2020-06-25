#! /usr/bin/env zsh

ENV=$1
EXCHANGE=$2
ENV_LOWERCASE=$(echo "${ENV}" | tr '[:upper:]' '[:lower:]')
ENV_UPPERCASE=$(echo "${ENV}" | tr '[:lower:]' '[:upper:]')


if [[ "$#" -ne 2 ]]; then
    echo "Usage: run_supervisor.sh <ENV> <EXCHANGE>"
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
    echo Launching a NerdSupervisor in ${ENV_UPPERCASE} environment

    do python -m market_maker.nerd_supervisor -e ${ENV_LOWERCASE} --exchange ${EXCHANGE} -i "SUPERVISOR"
    st=$?
    if [[ "$st" == "99"  ||  "$st" == "15" ]]; then
        echo "NerdSupervisor has finished with status code=${st} and the script will be terminated!"
        exit 0
    else
        echo "NerdSupervisor has finished and will be restarted: status code=${st}"
        sleep 5
    fi
done