#! /usr/bin/env zsh

NUMBER_OF_BOTS=$1
PROCESS_DELAY_SECONDS=10

run_bot_process() {
    _botid=${1}
    _number_of_bots=${2}
    ./run_bot.sh live ${_botid} ${_number_of_bots} &
}

cleanup() {
    pgrep -f "market_maker.mm_bot -e live --botid" | xargs kill
    pgrep -f "run_bot.sh live" | xargs kill
}

if [[ "$#" -ne 1 ]]; then
    echo "Usage: run_portfolio_live.sh <NUMBER OF BOTS>"
    exit 0
fi

if [[ "$1" == "stop" ]]; then
    echo "Stopping all NerdMarketMakerBot LIVE instances.."
    cleanup
    echo "Done!"
    sleep 3
    echo "Checking bot instances are still running:"
    ps -ef | grep bot
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

cleanup

echo Executing portfolio of NerdMarketMakerBot instances in LIVE environment ...

for (( i=1; i<=${NUMBER_OF_BOTS}; i++ ))
do
    botid=$(printf "Bot%03d" $i)

    run_bot_process ${botid} ${NUMBER_OF_BOTS}

    if [[ "${i}" -lt ${NUMBER_OF_BOTS} ]]; then
        sleep ${PROCESS_DELAY_SECONDS}
    fi

done

echo Executing NerdSupervisor in LIVE environment ...

./run_supervisor.sh test ${_number_of_bots} &
