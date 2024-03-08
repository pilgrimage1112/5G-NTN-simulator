#!/bin/bash

docker1=$1
broadcast_ip=$2
docker2=$3
delay=$4

dev_name=$(docker exec -id $docker1 ifconfig | grep -B 1 $broadcast_ip | head -n 1 | awk -F: '{print $1}')
dev_ip=$(docker exec -id $docker1 ifconfig | grep $broadcast_ip | awk '{print $2}')

count=$(docker exec -id $docker2 tc -s qdisc show dev eth1 | sed -n '4p' | awk '{split($5, a, ":"); print a[2]}')
next_count=$((10#$count+1))
# echo "docker1: $docker1"
# echo "broadcast_ip: $broadcast_ip"
# echo "dev_name: $dev_name "

docker exec -id $docker1 tc qdisc del dev $dev_name root netem
docker exec -id $docker1 tc qdisc add dev $dev_name root netem delay $delay
docker exec -id $docker2 tc qdisc add dev eth1 root handle 1: prio
docker exec -id $docker2 tc filter add dev eth1 protocol ip parent 1: prio 1 u32 match ip dst $dev_ip flowid 1:$next_count
docker exec -id $docker2 tc qdisc add dev eth1 parent 1:$next_count netem delay $delay

