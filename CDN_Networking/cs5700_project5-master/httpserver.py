#!/usr/bin/env python3

import socket
import os
import http.client
import subprocess
import sys
import gzip
import threading
import time
import signal

PORT = -1
ORIGIN_PORT = 8080
ORIGIN_HOST = ''
SOCK = None

DNS_KEY = 'jds1D41HPQ2110D85ef92jdaf341kdfasfk123154'

'''
Will be called as follows:

./httpserver -p <port> -o <origin>
'''

def handle_kill(*args):
    '''
    Closes the socket upon PID kill or terminating character

    :param args: None
    :return: None
    '''
    if SOCK is not None:
        SOCK.close()


def listen():
    '''
    Listens to request coming in from client

    :return: None
    '''
    global SOCK
    # Gets the host name
    hostname = socket.gethostname()
    # Gets the host IP Address
    ip_addr = socket.gethostbyname(hostname)

    # Creates a socket connection
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Binds socket to host IP Address and port
    sock.bind((ip_addr, PORT))
    # Listens on the socket connection for a request
    sock.listen(10)

    # collect sock in global variable so it can be closed on kill pid
    SOCK = sock
    # now that SOCK is socket, set handle_kill to close socket
    signal.signal(signal.SIGTERM, handle_kill)
    signal.signal(signal.SIGINT, handle_kill)

    # gets the connection and address
    while True:
        connection, address = sock.accept()
        # gets message from client
        message = connection.recv(1024)

        # parse the message to get the data
        # Name of the webpage
        resource = parseGET(message.decode())
        # check cache for content client is asking for

        # if looking for active measurements, start thread with measurements
        if resource == DNS_KEY:
            # create new thread so socket can continue to server requests
            measure_thread = threading.Thread(target=doActiveMeasurements, args=(connection, message))
            measure_thread.start()
        # otherwise, serve info from connection
        # no local writes, only reads, don't worry about locking
        else:
            serve_thread = threading.Thread(target=serveRequest, args=(connection, resource))
            serve_thread.start()


def serveRequest(connection: socket, resource):
    '''
    Serves a request from the server to the client.

    :param connection: socket object for given client
    :param resource: what the client is looking for
    :return: None
    '''
    # find the resource
    split_resource = resource.split('/')
    cache_return = None
    if len(split_resource) > 0:
        # get the file being looked for
        cache_resource = split_resource[-1]
        # search the cache for the given resource (without /wiki/ or any prior path)
        cache_return = cacheSearch(cache_resource + '.html.gz', '/cache_zip')
    # if found in cache, get that content from cache and send to client
    if cache_return is not None:
        # create 200 response and send back byte content to client
        connection.send(get200Response(len(cache_return)) + cache_return)
    else:
        # otherwise connect to origin and get content from there
        # sends entire resource, /wiki/<resource> or otherwise
        content = connectOrigin(resource)
        # if no error, return resposne from server, good or bad
        if content is not None:
            # send content from origin back to client
            connection.send(content)
        # if error with http.client - error returns None, send back manual "bad request"
        else:
            connection.send(getBadResponse().encode())

    # close connection
    connection.close()


def get200Response(size: int):
    '''
    Creates 200 response headers for cache hit.

    :param size: size of the content
    :return: headers for content request
    '''
    res_string = 'HTTP/1.1 200 OK\r\n'
    res_string += 'Content-Length: ' + str(size) + '\r\n'
    res_string += 'Content-Type: text/html; charset=UTF-8\r\n\r\n'

    return res_string.encode()


def getBadResponse():
    '''
    Creates bad request response when error with http.client request

    :return: header for bad request
    '''
    res_string = 'HTTP/1.1 400 BAD REQUEST\r\n\r\n'
    return res_string


def parseGET(request):
    '''
    Parse the GET request
    :param request: String HTTP GET request
    :return: The resource to be found
    '''
    # split by spaces
    request_list = request.split()
    # find the resource
    resource = request_list[1]
    return resource


def cacheSearch(resource, cache):
    '''
    Search through cache to see if resource is already stored
    :param cache:
    :param resource: resource/file name searching for
    :return: return content searching for, or return nothing
    '''
    # get path to the cache directory
    path = os.getcwd() + cache
    # get current list of files in the cache directory
    dir = os.listdir(path)

    # if empty directory
    if (len(dir) == 0):
        return None
    # otherwise if cache is not empty and
    # if the resource is in the cache directory
    elif resource in dir:
            # get entry for resource file
            index = dir.index(resource)
            file_dir = dir[index]
            # open file, get unzipped contents, close file and return contents
            f = gzip.open(os.getcwd() + '/cache_zip/' + file_dir, 'r')
            contents = f.read()
            f.close()

            # return contents
            return contents


def connectOrigin(request):
    '''
    Connects replica server to origin and foward client GET request
    :param request: String http get request from client
    :return:
    '''
    # try to connection to origin
    try:
        # connect to Origin
        conn = http.client.HTTPConnection(ORIGIN_HOST, ORIGIN_PORT)

        # set string to access from server
        access_content = 'http://' + ORIGIN_HOST + ':' + str(ORIGIN_PORT) + request
        # forward along GET request from client
        conn.request('GET', access_content)
        # get the response from origin
        t = conn.getresponse()

        # # if status is OK
        if t.status == 200:
            # return the string of the content to be added to the cache
            content = t.read()
            return get200Response(len(content)) + content
        # otherwise return response provided by server
        else:
            return b'HTTP/1.1 ' + str(t.status).encode() + b'\n' + t.headers.__bytes__()
    # otherwise return None to send back generic error response
    except http.client.HTTPException:
        return None


def doActiveMeasurements(connection: socket, client_ip_data: bytes):
    '''
    Performs active measurements on IPs given by DNS server

    :param connection: connection to DNS server
    :param client_ip_data: IPs to search for
    :return: None
    '''

    # get the formatted string with IPS
    info = client_ip_data.decode().split('\n')[-1]

    # split IPs and place into list, removing all empty spaces
    # split by '*' char
    ips = list(filter(None, info.split('*')))

    # create lock to add IP data concurrently
    ip_data_lock = threading.Lock()
    ip_data = []

    # create list to track all threads
    meas_threads = []

    # iterate through all IPs requested by DNS server
    for ip in ips:

        # if empty string, ignore
        if ip == '':
            continue

        # create a thread that probes the given IP address
        meas_thread = threading.Thread(target=measureClient, args=(ip, ip_data, ip_data_lock))
        meas_threads.append(meas_thread)
        meas_thread.start()

        # limit probes to 1 per second
        time.sleep(1)

    # wait for all threads to finish before sending data back
    for thread in meas_threads:
        thread.join()

    # format data to be sent back
    res_data = '--'.join(ip_data)

    # encode data and send back with 200 response
    res = res_data.encode()
    connection.send(get200Response(len(res)) + res)
    connection.close()


def measureClient(ip, ip_data, ip_data_lock: threading.Lock):
    '''
    Measures the RTT to the closest public server to the given client IP.

    :param ip: client IP to probe
    :param ip_data: holds rtts for all IPs requested by DNS server
    :param ip_data_lock: lock that prevents multi-write on ip_data
    :return: None
    '''

    # create new subporcess
    process = subprocess.Popen(['/bin/bash'],
                               shell=True,
                               stdin=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               stdout=subprocess.PIPE)
    # trace -q 1 specifies number of attempts per hop (1)
    # trace -w 1 specifies time to wait for response, set to 1, if more than 1 theres a problem, try diff route
    cmd = 'scamper -c "trace -q 1 -w 1" -i ' + ip + '\n'
    # send command and wait for response from subprocess
    out, err = process.communicate(cmd.encode())
    data = out.decode()

    # get all hops to destination server
    lines = data.split('\n')
    # work backwards from ip closest to host
    i = len(lines) - 1
    # denotes closest public IP to server in traceroute results
    closest_ip = ''
    # holds last private IP to server in traceroute results -- backup, refrain from relying on this
    last_private = None
    # holds information about last line checked
    line_data = []
    # work backwards from end of traceroute to find closest public ip too address
    while i >= 0:
        # get current line to evaluate
        line = lines[i]
        # get information about this hop
        line_data = list(filter(None, line.split(' ')))
        # if line data = 4, succeessful probe
        if len(line_data) == 4:
            # find IPv4 address fields
            fields = line_data[1].split('.')
            # if private or vm ip, continue searching
            if fields[0] == '10' \
                    or (fields[0] == '172' and 16 <= int(fields[1]) <= 31) \
                    or (fields[0] == '172' and fields[1] == '192') \
                    or (fields[0] == '100' and 64 <= int(fields[1]) <= 127):
                # collect private ip closest to client in case no public ips are found
                if last_private is None:
                    last_private = line_data
                i -= 1
                continue
            # else is public ip, use this as closest entry to un-pingable ip
            else:
                closest_ip = line_data[1]
                break
        i -= 1

    # if all private ip addresses, use ping from closest private ip to client
    if i < 0:
        # if no private ip addresses in traceroute, no route found, cannot validate this value
        # set to high number so it is not chosen
        if last_private is None:
            data_string = ip + '::999.99'
        # otherwise, get ping for closest private ip to destination
        else:
            data_string = ip + '::' + last_private[2]

        # lock ip_data list to write data for this client
        ip_data_lock.acquire()
        ip_data.append(data_string)
        ip_data_lock.release()
    # otherwise, public ip entry point has been found
    else:
        # ping the closest ip
        process = subprocess.Popen(['/bin/bash'],
                                   shell=True,
                                   stdin=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   stdout=subprocess.PIPE)
        cmd = 'scamper -c ping -i ' + closest_ip + '\n'
        out, err = process.communicate(cmd.encode())

        # decode results of ping
        ping_info = out.decode()
        # if no packets received, set ip to ping from traceroute - not great, but generally accurate
        # based on empirical findings
        if '0 packets received' in ping_info:
            data_string = ip + '::' + line_data[2]
        # otherwise, collect average
        else:
            avg_lat = ping_info.split('\n')[-2].split(' ')[3].split('/')[1]
            data_string = ip + '::' + avg_lat

        # lock ip_data list to write data for this client
        ip_data_lock.acquire()
        ip_data.append(data_string)
        ip_data_lock.release()


def main():
    '''
    Runs the http server.

    :return: None
    '''
    global ORIGIN_HOST
    global PORT

    # Receive HTTP GET request to local server from client
    # gets the port and origin from command line
    PORT = int(sys.argv[2])
    ORIGIN_HOST = sys.argv[4]
    # create the local cache directory
    listen()


# run the server
main()

