#! /usr/bin/env zsh

EXCHANGE=bitmex
NUMBER_OF_ROBOTS=2
PROCESS_DELAY_SECONDS=5  #  7200

run_robot_process() {
    _robotid=${1}
    _number_of_robots=${2}
    ./run_robot.sh live ${EXCHANGE} ${_robotid} ${_number_of_robots} &
}

cleanup() {
    pgrep -f "market_maker.mm_robot -e live" | xargs kill
    pgrep -f "market_maker.nerd_supervisor -e live" | xargs kill
    pgrep -f "run_robot.sh live" | xargs kill
    pgrep -f "run_supervisor.sh live" | xargs kill
}

if [[ "$1" == "stop" ]]; then
    echo "Stopping all NerdMarketMakerRobot LIVE instances.."
    cleanup
    echo "Done!"
    sleep 3
    echo "Checking robot instances are still running:"
    ps -ef | grep robot
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
for (( i=1; i<=${NUMBER_OF_ROBOTS}; i++ ))
do
    robotid=$(printf "Robot%03d" $i)

    run_robot_process ${robotid} ${NUMBER_OF_ROBOTS}

    sleep ${PROCESS_DELAY_SECONDS}

done

echo Executing NerdSupervisor in LIVE environment ...
./run_supervisor.sh live ${EXCHANGE} ${NUMBER_OF_ROBOTS} &
