from twisted.internet import protocol, reactor
from twisted.protocols import basic
import codecs
import json
import docker
import subprocess
import random
import string
from urllib.parse import quote

docker_client = None
ssh_container_nets = []
dirsNotAllowed = ["/", "/etc"]
routeNextRequestToCallback = None
newData = None





def enforceDisallowedDirs(dirs):
    # we get passed a list of hostdirs and compare them to the banlist
    if(dirs != None):
        for directory in map(lambda x : x.split(":")[0], dirs):
            if(len(directory) > 1 and directory[-1] == '/'):
                directory = directory[:-1] # remove pesky trailing slashes (for everything but / !)
            if(directory in dirsNotAllowed):
                return -1, directory # -1 is our uncool error code
    return 0, ""

def getNetwork(allData):
    pass

def buildResponse(responseDict, status):
    jsonString = json.dumps(responseDict)
    return bytearray("""HTTP/1.1 """ + str(status) + """
Api-Version: 1.39
Docker-Experimental: false
Ostype: linux
Content-Type: application/json
Content-Length: """ + str(len(jsonString)) + """

""" + jsonString, "UTF-8")

def associateContainerWithUser(containerHash):
    global docker_client

    printable = codecs.decode(containerHash, "unicode_escape")    
    chash = json.loads(printable.split("\n")[9])
    print(str(chash))
    c = docker_client.containers.get(chash)
    ssh_cont = docker_client.containers.get(ssh_container_hash)
    ssh_container_net.connect(c)

def commandRouter(url, data, allData):
    global routeNextRequestToCallback
    global ssh_container_net
    global newData
    spliturl = url.split("/")
    del spliturl[0]
    print(str(spliturl))
    if(len(spliturl) > 1):
        del spliturl[0]
        if(spliturl[0] == "containers"):
            if(len(spliturl) >= 2):
                if(spliturl[1] == "create"):
                    params = json.loads(data)
                    dirs = params["HostConfig"]["Binds"]
                    status, offendingDir = enforceDisallowedDirs(dirs)
                    if(status == -1):
                        return buildResponse({"message": "you are not allowed to bind " + str(offendingDir)}, 400)
                    else:
                        if("com.docker-rbac.user_admin" in params["Labels"].keys()):
                            network = docker_client.networks.create(''.join(random.choices(string.ascii_uppercase + string.digits, k=12)), driver="bridge", internal=True)
                            network.connect(ssh_cont)

                        def callback(containerHash, transport):
                            associateContainerWithUser(containerHash)
                            transport.write(containerHash)
                        routeNextRequestToCallback = callback
                elif(spliturl[1] == "json"): # docker ps
                    newurl = url + "?all=1"
                    newData = bytes("""GET /v1.39/containers/json?filters={%22network%22:[%22""" + ssh_container_net.name + """%22]} HTTP/1.1\r\nHost: localhost:2593\r\nUser-Agent: Docker-Client/18.09.2 (linux)\r\n\r\n""", "utf-8")
                    return 0
                else:
                    containerid = spliturl[1]
                    if(len(spliturl) >= 3):
                        action = spliturl[2]
                        action = action.split("?")
                        print("action is " + str(action))
                        if(action[0] == "attach"):
                            return buildResponse({"message": "attaching does not work yet"}, 400)
                        if(action[0] == "exec"):
                            return buildResponse({"message": "exec-ing does not work yet"}, 400)

                            
    return 1
        

def parseIncoming(data):
    line1 = data.split("\n")[0]
    restOfData = None
    for line in data.split("\n"):
        if(restOfData == 1):
            restOfData = line
        elif(restOfData == None):
            if(len(line.strip()) == 0):
                restOfData = 1
    method, url, _ = line1.split(" ")
    print("rest of data: \n" + str(restOfData))
    
    return commandRouter(url, restOfData, data)

class ServerProtocol(protocol.Protocol):
    def __init__(self):
        self.buffer = None
        self.client = None

    def connectionMade(self):
        factory = protocol.ClientFactory()
        factory.protocol = ClientProtocol
        factory.server = self
        reactor.connectTCP('localhost', 1234, factory)

    def dataReceived(self, data): # enroute to the docker daemon
        if (self.client != None):
            self.client.write(data)
        else:
            self.buffer = data

    def write(self, data): # back to the client cli proxy
        global routeNextRequestToCallback
        printable = codecs.decode(data, "unicode_escape")
        if(routeNextRequestToCallback != None and ("message") not in json.loads(printable.split("\n")[9]).keys() ):
            routeNextRequestToCallback(data, self.transport)
            routeNextRequestToCallback = None
        else:
            self.transport.write(data)
        printable = codecs.decode(data, "unicode_escape")
        print('SERVER: ' + printable)

class ClientProtocol(protocol.Protocol):
    def connectionMade(self):
        self.factory.server.client = self
        self.write(self.factory.server.buffer)
        self.factory.server.buffer = ''

    def dataReceived(self, data): # back to the cli
        self.factory.server.write(data)

    def write(self, data): # enroute to the docker daemon
        global newData
        if(len(data) > 0):
            printable = codecs.decode(data, "unicode_escape")
            status = parseIncoming(printable)
            print('CLIENT: ' + str(data))
            if(status == 1): # pass along information unchanged
                self.transport.write(data)
            elif(status == 0): # pass along modified info
                print("sending modified info:\n " + str(newData))
                self.transport.write(newData) 
            else: # fake being the server for errors and stuff
                print("should be returning some stuff to docker cli")
                self.dataReceived(status)

def setupContainers():
    global docker_client
    # global ssh_container_hash
    # global ssh_container_net
    # print(str(docker_client))
    # network = docker_client.networks.create(''.join(random.choices(string.ascii_uppercase + string.digits, k=12)), driver="bridge", internal=True)
    # ssh_cont = docker_client.containers.run(docker_client.images.get("ssh_cont"), ports={22:0}, detach=True)
    # ssh_container_hash = ssh_cont.id
    
    # ssh_container_net = network
    # ssh_cont.reload()
    #print("created ssh container on port " + str(ssh_cont.attrs["NetworkSettings"]["Ports"]["22/tcp"][0]["HostPort"]))
        

def main():
    global docker_client
    docker_client = docker.DockerClient(base_url='tcp://localhost:1234')
    setupContainers()
    factory = protocol.ServerFactory()
    factory.protocol = ServerProtocol
    
    reactor.listenTCP(2593, factory)
    reactor.run()

if __name__ == '__main__':
    
    print("cli port: 2593")
    print("dockerd port: 1234")
    main()