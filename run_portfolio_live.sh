#! /usr/bin/env zsh

ENV=live
EXCHANGE=bitmex
PROCESS_DELAY_SECONDS=5  #  7200

run_robot_process() {
    _robotid=${1}
    ./run_robot.sh live ${EXCHANGE} ${_robotid} &
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
while read robotid
do
    run_robot_process ${robotid}

    sleep ${PROCESS_DELAY_SECONDS}
done < <(python -m market_maker.db.get_enabled_robots -e ${ENV} -x ${EXCHANGE})

echo Executing NerdSupervisor in LIVE environment ...
./run_supervisor.sh ${ENV} ${EXCHANGE} &
