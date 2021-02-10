#!/usr/bin/env python3

import os
import http.client
import gzip
import sys
import threading

ACCESS_CONTENT = ''
ORIGIN_PORT = 8080
ORIGIN_HOST = ''

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
        # forward along GET request from client
        conn.request('GET', ACCESS_CONTENT + request)
        # get the response from origin
        t = conn.getresponse()
        # convert response into string and decode
        string = str(t.read().decode("utf-8"))
        # if status is OK
        if t.status == 200:
            # return the string of the content to be added to the cache
            return string
    # otherwise catch an error
    except http.client.HTTPException as error:
        print(error)

def addToCache(filename, data, write_lock: threading.Lock):
    '''
    Creating a file and adding to the cache
    :param filename: file name to be created and path
    :param data: data to be written to the file
    :return: size of current file
    '''
    if data == None:
        return 0

    write_lock.acquire()
    file = gzip.open(filename, 'w+')
    file.write(data.encode())
    file.close()
    write_lock.release()

    return os.path.getsize(filename)

def createDirectory():
    '''
    Creates the initial cache directory and load in the most viewed wiki webpages loaded in
    :return: N/A
    '''
    # try to create a local cache directory
    try:
        # directory name
        directory_cachezip = 'cache_zip'
        # get parent working directory
        parent_dir = os.getcwd()
        # join them
        path_zip = os.path.join(parent_dir, directory_cachezip)
        # create new cache directory
        os.mkdir(path_zip)
        fillCache()
    # catch file already exists error if cache directory already created
    except FileExistsError as error:
        fillCache()

def fillCache():
    '''
    Fill cache directory
    Return: N/A
    '''

    # go through most_viewed and add to cache
    fin = open("most_viewed_test.csv", "r")
    # get the lines from file
    lines = fin.readlines()
    # close the file
    fin.close()
    # go through lines-- current limit
    # fill zip cache
    write_lock = threading.Lock()
    for i in range(1, len(lines)):
        write_t = threading.Thread(target=fillThread, args=(lines[i], write_lock))
        write_t.start()


def fillThread(line, write_lock:threading.Lock):
    # split each of the lines again
    website = line.split(',')
    article = website[0]
    # get the article name
    article_name = article.split('/')[-1]
    # connect to the origin to get and store the content
    content = connectOrigin(article_name)
    # add the content to the cache
    addToCache(os.getcwd() + '/cache_zip/' + article_name + '.html.gz', content, write_lock)

def main():
    global ORIGIN_HOST
    global ACCESS_CONTENT

    if len(sys.argv) < 3:
        raise ValueError("Insufficient command line args")

    ORIGIN_HOST = sys.argv[2]
    ACCESS_CONTENT = 'http://' + ORIGIN_HOST + ':' + str(ORIGIN_PORT) + '/wiki/'

    createDirectory()


# run the cacheFill script
main()