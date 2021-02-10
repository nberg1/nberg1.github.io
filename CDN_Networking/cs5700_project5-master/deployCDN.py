#!/usr/bin/env python3

import subprocess
import sys
import threading


# list of EC2 servers
EC2_SERVERS = [
    'ec2-34-238-192-84.compute-1.amazonaws.com',                # N. Virginia
    'ec2-13-231-206-182.ap-northeast-1.compute.amazonaws.com',   # Tokyo
    'ec2-13-239-22-118.ap-southeast-2.compute.amazonaws.com',    # Sydney
    'ec2-34-248-209-79.eu-west-1.compute.amazonaws.com',         # Ireland
    'ec2-18-231-122-62.sa-east-1.compute.amazonaws.com',         # Sao Paulo
    'ec2-3-101-37-125.us-west-1.compute.amazonaws.com'          # N. California
]


def callDeploy():
    '''
    Calls the deploy to send executables to each of the running EC2 servers
    Return: N/A
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

    # the origin server is the 5th argument in command line
    o_index = sys.argv.index('-o')
    origin = sys.argv[o_index + 1]
    # the username to log into the EC2 server
    u_index = sys.argv.index('-u')
    username = sys.argv[u_index + 1]
    # file name where the key is stored
    i_index = sys.argv.index('-i')
    keyfile = sys.argv[i_index + 1]

    deploy_threads = []

    # go through each of the servers and create threading to allow
    # multiple processes to run simultaneously
    for server in EC2_SERVERS:
        server_thread = threading.Thread(target=callServerDeploy, args=(username, server, keyfile, origin))
        deploy_threads.append(server_thread)
        server_thread.start()

    scp_dest = username + '@cs5700cdnproject.ccs.neu.edu:/home/' + username + '/'
    scp_dns_server = 'scp -o StrictHostKeyChecking=no -i ' + keyfile + ' dnsserver ' + scp_dest + '\n'

    callSubProcess(scp_dns_server.split())

    ssh_dest = username + '@cs5700cdnproject.ccs.neu.edu'

    # run a get request for geolocation ip tar.gz file
    get_db = "wget -O ip_db.tar.gz \"https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=yihZe7a2Exa3ArYt&suffix=tar.gz\"\n"
    extract_tar = 'tar -zxf ip_db.tar.gz --wildcards */GeoLite2-City.mmdb --strip-components=1\n'
    remove_tar = 'rm -r ip_db.tar.gz\n'
    logout = 'logout\n'

    # commands to run in order
    ssh_cmds = [get_db, extract_tar, remove_tar, logout]

    # run the subprocesses

    # for each of the commands, run them on the servers in order
    for cmd in ssh_cmds:
        communicateSSH(cmd, keyfile, ssh_dest)

    for threads in deploy_threads:
        threads.join()


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


def callSubProcess(args):
    '''
    Calls and runs the subprocesses that each server should run simultaneously with eachother
    The args should be completed consecutively
    :param args: processes that should be run
    :return: Nothing to return
    '''
    subprocess.call(args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL)


def callServerDeploy(username, server, keyfile, origin):
    '''
    Method that logs in to each server and deploys the executable to run
    :param username: login username
    :param server: which server connecting to
    :param keyfile: file/location of the key for login
    :param origin: origin server hostname
    :return: N/A
    '''
    scp_dest = username + '@' + server + ':/home/' + username + '/'
    ssh_dest = username + '@' + server

    # send httpserver executable to specified EC2 server
    # turn off strict host keychecking on first contact w/ server, will add to known hosts lists at dns server
    scp_http_server = 'scp -o StrictHostKeyChecking=no -i ' + keyfile + ' httpserver ' + scp_dest + '\n'
    # send cache executable to specified EC2 server to fill cache
    scp_cache = 'scp -i ' + keyfile + ' cacheFill ' + scp_dest + '\n'
    # send text file of most viewed websites to the EC2 server to be used to populate the cache
    scp_sites = 'scp -i ' + keyfile + ' most_viewed_test.csv ' + scp_dest + '\n'
    # run the cacheFill executable to fill the cache with the most viewed websites
    run_cache_fill = './cacheFill -o ' + origin + '\n'
    # logout of the EC2 server
    logout = 'logout\n'

    # list of all the above commands
    all_cmds = [scp_http_server, scp_cache, scp_sites]  # ,

    # go through each of these commands and run them as subprocesses
    for cmd in all_cmds:
        callSubProcess(cmd.split())

    # commands to execute
    ssh_cmds = [run_cache_fill, logout]

    # for each of the commands, run as a subprocesses
    for cmd in ssh_cmds:
        communicateSSH(cmd, keyfile, ssh_dest)


# run the Deploy script
callDeploy()
