# !/usr/bin/python

import random
import logging
import logging.handlers
import time
import sys
import json
import requests_unixsocket

LOG_FILENAME = "kaos.log"

g_numRange = "2-10"
g_intervalRanage = "30-60"
g_victimType = "random"        # pod, container, random
g_action = "random"            # kill, stop, pause, restart, random
g_hurtSystemPods = True        # True/False

g_supportedActions = ["kill", "stop", "pause", "restart"]

# Add your system pods list here. This is a specific list of pods that are running for managing the k8s cluster. Populate this list if you want to save them from being hurt and set -hurtsystempods to yes
g_systemPods = [] # ["logging-daemon", "port-allocator", "calico", "kube-proxy", "kube-registry-proxy"]

g_self = "kaos"

class Container:
    def __init__(self):
        self.id = ""
        self.containername = ""
        self.podname = ""
        self.type = ""        # can be "pod" or "container". Pod in its bare shell is a container.

def get_victim_list():
    containerList = []
    podList = []
    
    # Get JSON list of containers on the node.
    session = requests_unixsocket.Session()
    resp = session.get("http+unix://%2Fvar%2Frun%2Fdocker.sock/v1.24/containers/json")
    print (resp.status_code)
    if resp.status_code >= 200 and resp.status_code < 300:
        logger.info("get_victim_list: Successfully fetched containers list from docker. HTTP code: " + str(resp.status_code))
        containers = json.loads(resp.text)
        for container in containers:
            c = Container()
            c.id = container["Id"]
            try:
                c.containername = container["Labels"]["io.kubernetes.container.name"]
                c.podname = container["Labels"]["io.kubernetes.pod.name"]
        
                if container["Labels"]["io.kubernetes.container.name"] == "POD":
                    c.type = "pod"
                    podList.append(c)
                else:
                    c.type = "container"
                    containerList.append(c)
            except Exception, e:
                logger.critical("get_victim_list: Labels not present in container, using empty name.Exception: ", exc_info=True)
                containerList.append(c)
    else:
        logger.error("get_victim_list: Failed to get containers list from docker. HTTP error: " + str(resp.status_code))
        
    return containerList, podList

def start_kaos():
    logger.info("start_kaos: Waking up the POnDa ...")
    
    # Now do this as a service, infinite loop until someone kills you!
    while 1:
        numToKill = getRandomInRange(g_numRange)
        intervalBetweenKills = getRandomInRange(g_intervalRanage)
        
        # Get the list of all pods/containers running
        logger.info("start_kaos: [NewKaosJob] Getting the list of all pods/containers running on the node ...")
        
        containerList, podList = get_victim_list()
        victimList = []
        if g_victimType == "pod":
            victimList = podList
        elif g_victimType == "container":
            victimList = containerList
        else:
            victimList = podList + containerList
            
        # Filter out system pods
        victimList = filterPods(victimList)
        
        # Shuffle the list
        random.shuffle(victimList)
        
        #pidList = getPIDList(True)
        if numToKill > len(victimList):
            numToKill = len(victimList)
        logger.info("start_kaos: Number of " + g_victimType + "s to hurt: " + str(numToKill))

        # hurt the last victim first
        victimList = victimList[(len(victimList)-numToKill):]
        logger.info("start_kaos: Taking action " + g_action + " on the following " + g_victimType + "s: ")
        victimNameList = ""
        for victim in victimList:
            victimNameList += victim.podname
            victimNameList += ", "
        logger.info(victimNameList)
        
        # Now is time to hurt these guys =)
        for victim in victimList:
            logger.info("start_kaos: Hurting " + victim.podname + " ...")
            hurtHim(victim)
            
        # sleep for the specific interval before next session
        logger.info("start_kaos: Sleeping for " + str(intervalBetweenKills) + "s before executing next session ...")
        time.sleep(intervalBetweenKills)

def filterPods(victimList):
    for victim in victimList:
        # Save from hurting self
        if victim.podname.find(g_self) != -1:
            victimList.remove(victim)
            
        # Now remove all system pods if they are to be saved.
        if g_hurtSystemPods == False:
            for systemPod in g_systemPods:
                if victim.podname.find(systemPod) != -1:
                    victimList.remove(victim)
                    break
        else:
            break
    return victimList
    
def hurtHim(victim):

    # Unpause the pod/container if it was paused during an earlier kaos session otherwise the container won't accept any new commands.
    unpauseIfPaused(victim)
    
    action = g_action
    if action == "random":
        action = g_supportedActions[random.randint(0, len(g_supportedActions)-1)]
    
    uri = ""
    if action == "kill":
        uri = "/containers/" + victim.id + "/kill"
    elif action == "stop":
        uri = "/containers/" + victim.id + "/stop"
    elif action == "pause":
        uri = "/containers/" + victim.id + "/pause"
    elif action == "restart":
        uri = "/containers/" + victim.id + "/restart"
    
    try:
        logger.debug("hurtHim: " + "http+unix://%2Fvar%2Frun%2Fdocker.sock/v1.24" + uri)
        session = requests_unixsocket.Session()
        resp = session.post("http+unix://%2Fvar%2Frun%2Fdocker.sock/v1.24" + uri)
        if resp.status_code >= 200 and resp.status_code < 300:
            logger.info("hurtHim: " + victim.type + " [ " + victim.podname + ", " + victim.id + " ] successfully applied with action: " + action)
        else:
            logger.error("hurtHim: Failed with action: " + action + ": on " + victim.type + " [" + victim.podname + "] with HTTP error: " + str(resp.status_code))
    except Exception, e:
        logger.critical("hurtHim: Failed with action: " + action + ": on " + victim.type + " [" + victim.podname + "] with Exception: ", exc_info=True)

def unpauseIfPaused(container):
    try:
        session = requests_unixsocket.Session()
        resp = session.get("http+unix://%2Fvar%2Frun%2Fdocker.sock/v1.24/containers/" + container.id + "/json")
        if resp.status_code >= 200 and resp.status_code < 300:
            containerDetails = json.loads(resp.text)
            if containerDetails["State"]["Status"] == "paused":
                resp = session.post("http+unix://%2Fvar%2Frun%2Fdocker.sock/v1.24/containers/" + container.id + "/unpause")
                if resp.status_code >= 200 and resp.status_code < 300:
                    logger.info("unpauseIfPaused: " + container.type + " [ " + container.podname + ", " + container.id + " ] successfully unpaused.")
                else:
                    logger.error("unpauseIfPaused: Failed to unpause " + container.type + " [" + container.podname + "] with HTTP error: " + str(resp.status_code))
        else:
            logger.error("unpauseIfPaused: Failed to fetch details (docker inspect) of " + container.type + " [" + container.podname + "] with HTTP error: " + str(resp.status_code))
    except Exception, e:
        logger.critical("unpauseIfPaused: Failed to unpause " + container.type + " [" + container.podname + "] with Exception: ", exc_info=True)

def getRandomInRange(strRange):
    numRange = strRange.split("-")    
    if len(numRange) == 0:
        logger.error("getRandomInRange: Error: Bad number range.")
        return 0
    else:
        numMin = int(numRange[0])
        numMax = numMin
        if len(numRange) == 2:
            numMax = int(numRange[1])
    
    return random.randint(numMin, numMax)

def scriptHelp():
    print "--------------------------------------------------"
    print "Usage : ./kaos-ponda.py [-OPTION=VAL]"
    print "\t-victim:         (pod, container, random)"
    print "\t-action:         (kill, stop, pause, restart, random)"
    print "\t-hurtsystempods: (yes, no) Default is yes."
    print "\t-num:            <Number of victims to kill in single shot. Can also be a range like 2-4>"
    print "\t-interval:       <Interval between two kaos sessions (secs). Can also be a range like 20-60>"
    print "\tExample Usage:   python kaos-POnDa.py -victim=random -action=random -hurtsystempods=no -num=5-10 -interval=10-20"
    print "--------------------------------------------------"


for option in sys.argv[1:]:
    if option.find('-victim=') != -1:
        g_victimType = str(option[8:])

    elif option.find('-action=') != -1:
        g_action = str(option[8:])

    elif option.find('-hurtsystempods=') != -1:
        if str(option[16:]) == "yes":
            g_hurtSystemPods = True
        else:
            g_hurtSystemPods = False
            
    elif option.find('-num=') != -1:
        g_numRange = str(option[5:])

    elif option.find('-interval=') != -1:
        g_intervalRanage = option[10:]
        
    elif option.find('-h') != -1 or option.find('--help') != -1 or option.find('/h') != -1 or option.find('/help') != -1 or option.find('/?') != -1 or option.find('-?') != -1:
        scriptHelp()
        sys.exit()

# Set up a specific logger with our desired output level
logFormatter = logging.Formatter("[%(asctime)s] [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
logger = logging.getLogger()
logger.setLevel(logging.NOTSET)

# Add console handler
consoleHandler = logging.StreamHandler(sys.stdout)
consoleHandler.setLevel(logging.NOTSET)
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)

# Add the log message handler to the logger
handler = logging.handlers.RotatingFileHandler(LOG_FILENAME,
                                               maxBytes=104857600,
                                               backupCount=20,
                                               )
handler.setFormatter(logFormatter)
logger.addHandler(handler)

start_kaos()
