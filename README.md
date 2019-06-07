# kaos-POnDa
Chaos monkey style testing for Kubernetes PODs. It will bring chaos on the node (host) where it runs by killing/stopping/restarting/pausing pods/containers randomly or as defined by cmd like config.


## Description
kaos-ponda derives it's name from "Chaos" and "Panda", mimicking "Chaos-Monkey". 
It can be run as a standalone script or within a container/pod in the k8s cluster. kaos-ponda will impact the node/host where the container runs and will kill/stop/restart/pause the containers or pods as configured. 

## Usage
```
Usage : ./kaos-ponda.py [-OPTION=VAL]
	-victim:         (pod, container, random)
	-action:         (kill, stop, pause, restart, random)
	-hurtsystempods: (yes, no) Default is yes.
	-num:            <Number of victims to kill in single shot. Can also be a range like 2-4>
	-interval:       <Interval between two kaos sessions (secs). Can also be a range like 20-60>
```
#### Example Usage
>`python kaos-POnDa.py -victim=random -action=random -hurtsystempods=no -num=5-10 -interval=10-20`


