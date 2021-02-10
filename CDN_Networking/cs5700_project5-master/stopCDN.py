#!/usr/bin/env python3

import subprocess
import sys

# list of all EC2 servers
import threading

EC2_SERVERS = [
    'ec2-34-238-192-84.compute-1.amazonaws.com',                # N. Virginia
    'ec2-13-231-206-182.ap-northeast-1.compute.amazonaws.com',   # Tokyo
    'ec2-13-239-22-118.ap-southeast-2.compute.amazonaws.com',    # Sydney
    'ec2-34-248-209-79.eu-west-1.compute.amazonaws.com',         # Ireland
    'ec2-18-231-122-62.sa-east-1.compute.amazonaws.com',         # Sao Paulo
    'ec2-3-101-37-125.us-west-1.compute.amazonaws.com'          # N. California
]


def stop():
    '''
    Stop method that ends execution on the EC2 server and removes any files from the server.

    :return None
    '''
    # Checks to ensure the correct amount of arguments are included in the command call
    if len(sys.argv) < 11:
        raise ValueError('Insufficient command line arguments provided')
    elif '-p' not in sys.argv \
            or '-o' not in sys.argv \
            or '-n' not in sys.argv \
            or '-u' not in sys.argv \
            or '-i' not in sys.argv:
        raise ValueError('Missing required flags in command line arguments')

    # login username
    u_index = sys.argv.index('-u')
    username = sys.argv[u_index + 1]
    # file/location of private key used for login
    i_index = sys.argv.index('-i')
    keyfile = sys.argv[i_index + 1]

    replica_servers = []

    # for each of the servers
    for server in EC2_SERVERS:
        clean_thread = threading.Thread(target=cleanReplicaServers, args=(username, server, keyfile))
        replica_servers.append(clean_thread)
        clean_thread.start()

    # kill dnsserver command
    dns_kill_cmd = 'kill $(cat dns_pid.txt)\n'
    # remove document from dnsserver
    dns_rmv_cmd = 'rm dns_pid.txt\n'

    pid_rmv_cmd = 'rm dnsserver\n'
    # remove geolocation library
    remove_db = 'rm GeoLite2-City.mmdb\n'
    logout = 'logout\n'

    # list all the commands in order of execution
    dns_cmds = [dns_kill_cmd, dns_rmv_cmd, pid_rmv_cmd, remove_db, logout]

    ssh_dest = username + '@cs5700cdnproject.ccs.neu.edu'

    # for each of the commands, write them to the command line and then run it
    for cmd in dns_cmds:
        communicateSSH(cmd, keyfile, ssh_dest)

    # wait for all threads to finish before leaving stop
    for thread in replica_servers:
        thread.join()


def communicateSSH(command, keyfile, ssh_dest):
    '''
    Writes commands to ssh subprocess. Prints output and errors to console.
    '''
    subp = subprocess.Popen(['ssh', '-i', keyfile, ssh_dest],
                            shell=False,
                            stdout=subprocess.PIPE,
                            stdin=subprocess.PIPE,
                            stderr=subprocess.PIPE)

    out, err = subp.communicate(command.encode())

    if out:
        print(out)
    if err:
        print(err)


def cleanReplicaServers(username, server, keyfile):
    # get the destination server (login username and server ip)
    dest = username + '@' + server

    # kill command to kill execution
    kill_cmd = 'kill $(cat http_pid.txt)\n'
    # remove command to delete pid text file
    rmv_cmd = 'rm http_pid.txt\n'
    # remove command to delete cache directory and all files within
    rm_cache = 'rm -r cache_zip\n'
    # remove executable to fill cache
    rm_cache_fill = 'rm cacheFill\n'
    # remove executable to run httpserver
    rm_httpserver = 'rm httpserver\n'
    # remove command to delete the list of most viewed websites that were cached
    rm_most_viewed = 'rm most_viewed_test.csv\n'
    # logout
    logout = 'logout\n'
    # list of the commands in order of execution
    all_cmds = [kill_cmd, rmv_cmd, rm_cache, rm_cache_fill,
                rm_httpserver, rm_most_viewed, logout]

    # for each of the commands, write as terminal command and run it
    for cmd in all_cmds:
        communicateSSH(cmd, keyfile, dest)


stop()

