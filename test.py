import socket

ip = '192.168.1.1'
ip_int = int.from_bytes(socket.inet_aton(ip),byteorder='big')
ip_int_str = socket.inet_ntoa(int.to_bytes(ip_int, length=4, byteorder='big'))
print(ip_int, ip_int_str)
print(type(ip_int_str))