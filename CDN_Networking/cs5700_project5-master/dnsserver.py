#!/usr/bin/env python3

import sys
import socket
import dns.query
import dns.message
import dns.rrset
import threading
import geoip2.database
import math
import http.client
import time
import signal

# maxmind key: yihZe7a2Exa3ArYt
# key 2 : LSgtQJ3m5zjp0Ui5

# get database commands
# wget -O ip_db.tar.gz 'https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-ASN&license_key=yihZe7a2Exa3ArYt&suffix=tar.gz'
# tar -zxf ip_db.tar.gz --wildcards */GeoLite2-ASN.mmdb --strip-components=1
# rm -r ip_db.tar.gz

# https://programtalk.com/python-examples/dns.message.make_response/
# https://dnspython.readthedocs.io/en/latest/query.html

# -p 40020 -n cs5700cdn.example.com

# raw ip addresses of ec2 instances
EC2_IPS = [
    '34.238.192.84',        # N. Virginia
    '13.231.206.182',       # Tokyo
    '13.239.22.118',        # Sydney
    '34.248.209.79',        # Ireland
    '18.231.122.62',        # Sao Paulo
    '3.101.37.125'          # N. California
]

# geolocations for ec2 ip addresses
# tuple (latitude, longitude, ip address)
EC2_GEOLOCATIONS = [
    (39.0481, -77.4728, '34.238.192.84'),           # N. Virginia
    (35.685, 139.7514, '13.231.206.182'),           # Tokyo
    (-33.8612, 151.1982, '13.239.22.118'),          # Sydney
    (53.3331, -6.2489, '34.248.209.79'),            # Ireland
    (-23.5733, -46.6417, '18.231.122.62'),          # Sao Paulo
    (37.33053, -121.83823, '3.101.37.125')          # N. California
]

# dictionary containing client ip addresses and the last
# replica server they were sent to
# key=client_ip, value=replica_ip
CLIENT_IP_GEO = {}

# contains active measurments for a server
# key=ip address, value=rtt
CLIENT_IP_RTT = {}

# holds client ips that have accessed the server
CLIENT_IP = set()

# key for ec2 to identify dns server
DNS_KEY = 'jds1D41HPQ2110D85ef92jdaf341kdfasfk123154'

# holds socket for kill via PID
SOCK = None

# will stop thread
STOP_MEAS = False


def handle_kill(*args):
    global STOP_MEAS
    STOP_MEAS = True
    if SOCK is not None:
        SOCK.close()


def listen():
    '''

    '''
    global SOCK

    # Checks to ensure the correct amount of arguments are included in the command call
    if len(sys.argv) < 5:
        raise ValueError('Insufficient command line arguments provided')
    # Check to make sure commands arguments are in correct order
    if sys.argv[1] == '-p' and sys.argv[3] == '-n':
        # assign port and name of dns server
        port = sys.argv[2]
        name = sys.argv[4]
    elif sys.argv[3] == '-p' and sys.argv[1] == '-n':
        # assign port and name of dns server
        port = sys.argv[4]
        name = sys.argv[2]
    else:
        raise ValueError("Bad command line arguments provided")
    # Error check and make sure port is an integer
    try:
        port = int(port)
    except ValueError:
        raise ValueError('Port must be an integer')

    # get the hostname
    hostname = socket.gethostname()
    # get the ip address of for host
    name_ip = socket.gethostbyname(hostname)
    # create socket connection
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # bind socket connection to the host ip address at the specified port #
    sock.bind((name_ip, port))

    # collect sock in global variable so it can be closed on kill pid
    SOCK = sock
    # now that SOCK is socket, set handle_kill to close socket
    signal.signal(signal.SIGTERM, handle_kill)
    signal.signal(signal.SIGINT, handle_kill)

    rtt_lock = threading.Lock()
    client_lock = threading.Lock()
    geo_ip_lock = threading.Lock()
    active_meas_thread = threading.Thread(target=doActiveMeasurements, args=(port, rtt_lock, client_lock, geo_ip_lock))
    active_meas_thread.start()
    # doActiveMeasurements(port, rtt_lock, client_lock)

    while True:
        # get query
        val = dns.query.receive_udp(sock)

        # pull the Question from the Message
        question = val[0].question[0]

        # get requested server hostname
        q_name = question.name
        str_q_name = str(q_name)

        # if requested name is not name handed to server,
        # bad name, not for our dns
        if str_q_name[:-1] != name:
            continue

        # get the closest server to client
        # acquire active lock in case its being written to in active measurements
        has_rtt_val = False
        rtt_lock.acquire()
        if val[2][0] in CLIENT_IP_RTT:
            closest_ip = CLIENT_IP_RTT[val[2][0]]
            has_rtt_val = True
        rtt_lock.release()

        # if not rtt val was found, check for geo val
        # will allow for locking mechanism later on
        has_geo_val = False
        # lock geo_ip in case of concurrent reading in active measurement thread
        geo_ip_lock.acquire()
        if not has_rtt_val and val[2][0] in CLIENT_IP_GEO:
            closest_ip = CLIENT_IP_GEO[val[2][0]]
            has_geo_val = True
        geo_ip_lock.release()

        # if not rtt val or geo val was found, search for geo val
        if not has_rtt_val and not has_geo_val:
            closest_ip = getClosestServer(val[2][0])
            # lock geo_ip in case of concurrent reading in active measurement thread
            geo_ip_lock.acquire()
            CLIENT_IP_GEO[val[2][0]] = closest_ip
            geo_ip_lock.release()

        # lock CLIENT_IPS in case active measurement thread is reading from CLIENT_IP
        client_lock.acquire()
        if val[2][0] not in CLIENT_IP:
            CLIENT_IP.add(val[2][0])
        client_lock.release()

        # Create Answer -->
        # (Question name (queried hostname), 128 ttl, 'IN' rdclass, 'A' rdtype,
        # replica ip (where to go))
        answer = dns.rrset.from_text(q_name, 128, 'IN', 'A', closest_ip)
        # make reesponse from init message (adds RQ flag to response)
        res = dns.message.make_response(val[0])
        # add Answer to response
        res.answer.append(answer)
        # send answer back to requesting client (addr tuple in val[2])
        dns.query.send_udp(sock, res, val[2])


#-------- GEO LOCATION ---------------#

def findGeoLocation(ip):
    '''
    Finds the geolocation
    :param ip: ip address of client
    :return: latitude and longitude
    '''

    # probe database for provided IP
    reader = geoip2.database.Reader('./GeoLite2-City.mmdb')
    response = reader.city(ip)

    # collect longitude and latitude from response from database
    latitutde = response.location.latitude
    longitude = response.location.longitude

    # return (long, lat) as tuple
    return latitutde, longitude


def getClosestServer(ip):
    '''
    Find the closest server to the client
    :param ip: ip address of client
    :param: closest server to the client
    '''

    # get the latitude and longitude of the client
    lat, long = findGeoLocation(ip)

    # get a server
    closest = EC2_GEOLOCATIONS[0][2]
    # make dist HUGEEE
    dist = (1 << 32)

    # for each of the locations in geolocations, find the closest
    for locations in EC2_GEOLOCATIONS:
        curr_dist = math.sqrt(math.pow(abs(lat - locations[0]), 2) + math.pow(abs(long - locations[1]), 2))
        if curr_dist < dist:
            dist = curr_dist
            closest = locations[2]

    return closest


#------------ACTIVE MEASUREMENT JUNK--------------


def doActiveMeasurements(port, rtt_lock: threading.Lock, client_lock: threading.Lock, geo_ip_lock: threading.Lock):
    '''
    Runs active measurements to gather RTT information about client ips.

    :param port: port to connect to http server on
    :param rtt_lock: locks information regarding to client_rtts for multithread read/write
    :param client_lock: locks information regarding client IPs for multithread read/write
    :return: None
    '''

    # initially, wait for digs to populate client addresses - wait 10 seconds
    time.sleep(10)

    # repeat this action for duration of program
    while not STOP_MEAS:

        # store start time of current probe set
        start_time = time.time()

        # generate collection of client IPS
        # lock for CLIENT_IP -- parent thread writes to this, get state as currently is
        client_lock.acquire()
        client_ip_data = ''
        for each in CLIENT_IP:
            client_ip_data += '*' + each
        client_lock.release()

        # replica lock is used to write to client_rtts in each thread for each replica
        replica_lock = threading.Lock()
        client_rtts = {}

        # collect all threads in list to wait for them to finish
        threads = []

        for ip in EC2_IPS:
            client_rtts[ip] = []
            # send to http and get response
            meas_thread = threading.Thread(target=doActiveMeasurement, args=(ip, client_ip_data, port, client_rtts, replica_lock))
            # add thread to list of active threads
            threads.append(meas_thread)
            # start thread
            meas_thread.start()

        # wait for all threads to finish before writing
        for thread in threads:
            thread.join()

        # holds best times
        # key: client ip, value: tuple(rtt, ec2 ip)
        best_times = {}

        # iterate through ec2 ip results
        for ec2_ip in client_rtts.keys():
            # get results for all clients for current ec2
            ec2_results = client_rtts[ec2_ip]
            # iterate through results
            # results: tuple(client ip, rtt)
            for results in ec2_results:
                # if client ip has no record in best times, make one
                # assign rtt as first val of tuple, ec2 ip as second val
                if results[0] not in best_times:
                    best_times[results[0]] = (results[1], ec2_ip)
                else:
                    # otherwise, get the current best time for the client ip
                    curr_best = best_times[results[0]][0]
                    # get the rtt for the current result
                    curr_rtt = results[1]
                    # if rtt for curent result is lower than best
                    if float(curr_rtt) < float(curr_best):
                        # replace entry for client ip with rtt for result and associated ec2 address
                        best_times[results[0]] = (results[1], ec2_ip)

        # iterate throguh client ip results (keys in best_times)
        for client_ip in best_times:

            # if the best time is over 999ms ping, problem contacting server from all replicas
            # set to closest geo IP instead
            if float(best_times[client_ip][0]) >= 999:
                geo_ip_lock.acquire()
                CLIENT_IP_RTT[client_ip] = CLIENT_IP_GEO[client_ip]
                geo_ip_lock.release()
            # set client ip to correspond to the ec2 instance with the best time
            # lock global CLIENT_IP_RTT to prevent data race with requesting clients in main thread
            else:
                rtt_lock.acquire()
                CLIENT_IP_RTT[client_ip] = best_times[client_ip][1]
                rtt_lock.release()

        # calculate time to wait -- run every 30 seconds at minimum
        end_time = time.time()
        wait_val = 30 - (end_time - start_time)
        if wait_val < 0:
            wait_val = 0

        # wait given time seconds in between probes to re-measure network
        time.sleep(wait_val)


def doActiveMeasurement(ec2_ip, client_ip_data, port, client_rtts, replica_lock: threading.Lock):
    '''
    Requests active measurment data for specific ec2 http server.

    :param ec2_ip: ip address of ec2 http server
    :param client_ip_data: ips to request RTTs for
    :param port: port to connect to http server on
    :param client_rtts: holds information about rtts for client
    :param replica_lock: locks client_rtts for multithread read/write
    :return: None
    '''

    # connect to http server at ec2 ip address
    conn = http.client.HTTPConnection(ec2_ip, port)

    # request active measurment data
    conn.request('GET', DNS_KEY, client_ip_data)

    # get the response from the server
    res = conn.getresponse()

    # if 200 status, good response
    if res.status == 200:
        # parse data here and place in client_rtt data
        data = res.read().decode()
        ip_rtts = list(filter(None, data.split('--')))
        for rtts in ip_rtts:
            info = rtts.split('::')
            # append (client ip, rtt) to list at entry for ec2 ip
            # enact lock hear to write to client_rtts from parent thread doActiveMeasurements
            replica_lock.acquire()
            client_rtts[ec2_ip].append((info[0], info[1]))
            replica_lock.release()


# run dns server
listen()
