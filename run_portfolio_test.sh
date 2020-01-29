#! /bin/bash

NUMBER_OF_BOTS=$1
PROCESS_DELAY_SECONDS=10 #7200

run_bot_process() {
    _botid=${1}
    _number_of_bots=${2}
    ./run_bot.sh test ${_botid} ${_number_of_bots} &
}

cleanup() {
    kill $(pgrep -f "marketmaker.py --botid")
    kill $(pgrep -f "run_bot.sh test")
}

if [ "$#" -ne 1 ]; then
    echo "Usage: run_portfolio_test.sh <NUMBER OF BOTS>"
    exit 0
fi

if [ "$1" == "stop" ]; then
    echo "Stopping all NerdMarketMaker TEST bot instances.."
    cleanup
    echo "Done!"
    sleep 3
    echo "Checking bot instances are still running:"
    ps -ef | grep bot
    exit 0
fi

cleanup

echo Executing portfolio of NerdMarketMaker bot instances in TEST environment ...

for (( i=1; i<=${NUMBER_OF_BOTS}; i++ ))
do
     botid=$(printf "Bot%03d" $i)

     run_bot_process ${botid} ${NUMBER_OF_BOTS}
     sleep ${PROCESS_DELAY_SECONDS}

done
