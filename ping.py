import os
import socket
hostname=socket.gethostname()
ip=socket.gethostbyname(hostname)
print("System information\n")
print("Hostname is ",hostname)
print("IP is ",ip)
print("Ping the Network\n")
os.system("ping google.com")


#network tracing
