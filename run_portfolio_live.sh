#! /usr/bin/env zsh

EXCHANGE=bitmex
NUMBER_OF_BOTS=8
PROCESS_DELAY_SECONDS=7200 # 10

run_bot_process() {
    _botid=${1}
    _number_of_bots=${2}
    ./run_bot.sh live ${EXCHANGE} ${_botid} ${_number_of_bots} &
}

cleanup() {
    pgrep -f "market_maker.mm_bot -e live" | xargs kill
    pgrep -f "market_maker.nerd_supervisor -e live" | xargs kill
}


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

    sleep ${PROCESS_DELAY_SECONDS}

done

echo Executing NerdSupervisor in LIVE environment ...

./run_supervisor.sh live ${NUMBER_OF_BOTS} &
