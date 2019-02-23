from twisted.internet import protocol, reactor
from twisted.protocols import basic
import codecs

class ServerProtocol(protocol.Protocol):
    def __init__(self):
        self.buffer = None
        self.client = None

    def connectionMade(self):
        factory = protocol.ClientFactory()
        factory.protocol = ClientProtocol
        factory.server = self

        reactor.connectTCP('localhost', 1234, factory)

    def dataReceived(self, data):
        if (self.client != None):
            self.client.write(data)
        else:
            self.buffer = data

    def write(self, data):
        self.transport.write(data)
        printable = codecs.decode(data, "unicode_escape")
        print('Server: ' + printable)

class ClientProtocol(protocol.Protocol):
    def connectionMade(self):
        self.factory.server.client = self
        self.write(self.factory.server.buffer)
        self.factory.server.buffer = ''

    def dataReceived(self, data):
        self.factory.server.write(data)

    def write(self, data):
        self.transport.write(data)
        printable = codecs.decode(data, "unicode_escape")
        print('Client: ' + printable)

def main():

    factory = protocol.ServerFactory()
    factory.protocol = ServerProtocol

    reactor.listenTCP(2593, factory)
    reactor.run()

if __name__ == '__main__':
    main()