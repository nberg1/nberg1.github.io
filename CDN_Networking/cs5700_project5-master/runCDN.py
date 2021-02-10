#!/usr/bin/env python3

import subprocess
import sys
import threading

# list of all EC2 servers
EC2_SERVERS = [
    'ec2-34-238-192-84.compute-1.amazonaws.com',                # N. Virginia
    'ec2-13-231-206-182.ap-northeast-1.compute.amazonaws.com',   # Tokyo
    'ec2-13-239-22-118.ap-southeast-2.compute.amazonaws.com',    # Sydney
    'ec2-34-248-209-79.eu-west-1.compute.amazonaws.com',         # Ireland
    'ec2-18-231-122-62.sa-east-1.compute.amazonaws.com',         # Sao Paulo
    'ec2-3-101-37-125.us-west-1.compute.amazonaws.com'          # N. California
]


def run():
    '''
    Run scripts for the DNS and HTTP replica servers.

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

    # port to connect on
    p_index = sys.argv.index('-p')
    port = sys.argv[p_index + 1]
    # origin server
    o_index = sys.argv.index('-o')
    origin = sys.argv[o_index + 1]
    # name of requesting website
    n_index = sys.argv.index('-n')
    name = sys.argv[n_index + 1]
    # login username
    u_index = sys.argv.index('-u')
    username = sys.argv[u_index + 1]
    # file/location of private key used for login
    i_index = sys.argv.index('-i')
    keyfile = sys.argv[i_index + 1]

    # create collection to monitor server threads
    replica_threads = []

    # for each of the servers in the EC2 server list
    for server in EC2_SERVERS:
        replica_deploy = threading.Thread(target=deployReplica, args=(username, server, port, origin, keyfile))
        replica_threads.append(replica_deploy)
        replica_deploy.start()

    # create run command for dnsserver to automatically run the executable on the dnsserver
    run_dns = './dnsserver -p ' + port + ' -n ' + name + ' &>/dev/null & echo $! > dns_pid.txt\n'
    exit = 'logout\n'

    ssh_dest = username + '@cs5700cdnproject.ccs.neu.edu'

    # commands to run in order
    ssh_cmds = [run_dns, exit]

    # write the command as a terminal command and run it
    for cmd in ssh_cmds:
        communicateSSH(cmd, keyfile, ssh_dest)

    # wait for all replica deployment threads to finish
    for thread in replica_threads:
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


def deployReplica(username, server, port, origin, keyfile):
    # get the destination server (login username and server)
    dest = username + '@' + server
    # create run command for httpserver to automatically run the executable on the EC2 server
    run_cmd = './httpserver -p ' + port + ' -o ' + origin + '&>/dev/null & echo $! > http_pid.txt\n'
    logout = 'logout\n'

    all_cmds = [run_cmd, logout]

    # for each of the commands, take it in as a terminal command and run it
    for cmd in all_cmds:
        communicateSSH(cmd, keyfile, dest)


# run the Run script
run()

