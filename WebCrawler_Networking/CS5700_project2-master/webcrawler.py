#!/usr/bin/python
import socket
import sys
from HTMLParser import HTMLParser

# constants for connecting to/ receiving from server
HOST_URL = 'cs5700fa20.ccs.neu.edu'
PORT = 80
BUFF_SIZE = 256

# entry points and tokens
START_PAGE = '/fakebook/'
LOGIN_PAGE = '/accounts/login/?next=/fakebook/'
FLAG_START = 'FLAG: '
COOKIE_START = 'csrftoken='
COOKIE_END = ';'
SESSION_START = 'sessionid='
LOCATION_START = 'Location: '

# global variables to be used
csrftoken = []  # csrftoken values
session = []    # session id values
flags = []      # secret flags captured
pages = []      # pages to be visited
visited = []    # pages already visited
locations = []  # locations provided by 301 response

'''
my HTML Parser class to be used to parse HTML tags and data
'''
class myHTMLparser(HTMLParser):
    # used to keep track of depth of tag
    recording = 0

    # handles start tags
    def handle_starttag(self, tag, attrs):
        # search for h2 that has secret_flag attrib
        if tag == 'h2':
            for attr in attrs:
                if attr[0] == 'class' and attr[1] == 'secret_flag':
                    # increment recording var so know when to store that specific data
                    self.recording += 1
        # otherwise set recording back to 0
        else:
            self.recording = 0
        # go through all other attribs
        for attr in attrs:
            # search for attrib that has href indicating another URL to visit
            if attr[0] == 'href':
                # get that URL
                page = attr[1]
                # as long as not empty page and it has not been visited or is in page stack
                if page != '/' and page not in pages and page not in visited:
                    # as long as it is a URL from the root
                    if page[0].startswith('/'):
                        # append to pages array
                        pages.append(attr[1])

    # handles end tags
    def handle_endtag(self, tag):
        # if reach h2 tag and attrib is secret_flag as inidicated by recording == 1
        if tag == 'h2' and self.recording:
            # decrement the recording back to 0
            self.recording -= 1

    # handle data between tags
    def handle_data(self, data):
        # if recording is 1
        if self.recording:
            # flag is found. append flag data to flags array
            flags.append(data[len(FLAG_START):])

        # get csrftoken and session id data
        if 'HTTP/1.1' in data:
            # parse the data
            data_arr = data.split('\r\n')
            # go through each
            for each in data_arr:
                # if either the csrf token or session cookie is in the current data
                if (COOKIE_START in each) or (SESSION_START in each):
                    # parse it
                    tokens = each.split(COOKIE_END)
                    # get the token
                    token = tokens[0]
                    # parse
                    cookie = token[12:]
                    # put into appropriate array csrftoken or session
                    if cookie[:10] == COOKIE_START:
                        csrftoken.append(cookie[10:])
                    else:
                        session.append(cookie[10:])
                # if there is a location tag, set the global locations list to consist of
                # single found location page
                if LOCATION_START in each:
                    global locations
                    locations = [each[42:len(each)]]


'''
Name: parser
Parameters:
    html - String value of the html data returned from the GET/POST requests
    start_phrase - (String) which value to be returned; csrftoken, session id, or next page to be visited
Use: Calls the HTML parser, parses the tags and data, and stores cookies, pages to visit, and flags
Return: String value of either csrftoken, session id, or next page to be visited
'''
def parser(html, start_phrase):
    # instantiate HTMLParser object
    my_parser = myHTMLparser()
    # feed by parser object the html string
    my_parser.feed(html)
    try:
        # return the most recent csrftoken
        if start_phrase == COOKIE_START:
            return csrftoken[-1]
        # return the most recent session id value
    except IndexError:
        raise ValueError("CSRF token cannot be parsed")
    try:
        if start_phrase == SESSION_START:
            return session[-1]
    except IndexError:
        raise ValueError("Session id cannot be parsed")
    try:
        if start_phrase == LOCATION_START:
            return locations[-1]
    except IndexError:
        raise ValueError("Location response header cannot be parsed")


'''
Name: sendGET
Parameters:
    _file - (String) URL to send the GET request to
    cookie - (String) csrf token value
    session - (String) session id value
Use: Builds the GET request data to be sent to URL 
Return: String of the GET request data
'''
def sendGET(_file, cookie, _session):
    # Build the GET request String passing in the URL, csrf token, and session id
    request = 'GET ' + _file + ' HTTP/1.0\r\n'
    request += 'Cookie: csrftoken=' + cookie + '; sessionid=' + _session + '\r\n\r\n'
    return request

'''
Name: SendInitialGet
Parameters:
    _file - (String) URL to send the GET request to
Use: Builds the initial GET request to get initial session id and 
'''
def sendInitialGET(_file):
    # Build the GET request String passing in the URL, csrf token, and session id
    request = 'GET ' + _file + ' HTTP/1.0\r\n\r\n'
    return request

'''
Name: login
Parameters:
    _file - (String) URL to send POST request to
    csrf - (String) csrf token value
    session - (String) session id value
    username - (String) username for login
    password - (String) password for login
Use: Builds POST request string
Return: String of compiled POST request
'''
def login(_file, csrf, _session, username, password):
    login_info = 'username=' + username + '&password=' + password + '&csrfmiddlewaretoken=' + csrf
    con_len = len(login_info)
    # POST header & POST data request to be sent
    login_message = 'POST ' + _file + ' HTTP/1.0\r\n'
    login_message += 'Content-Length: ' + str(con_len) + '\r\n'
    login_message += 'Content-Type: application/x-www-form-urlencoded\r\n'
    login_message += "Cookie: csrftoken=" + csrf + '; sessionid=' + _session + '\r\n'
    login_message += '\r\n'
    login_message += login_info + '\r\n'
    return login_message


'''
Name: sendMessage
Parameters:
    message - (String) HTTP request to be sent
Use: Sends the HTTP request through socket and receives HTML data in return
Return: String of data received from the HTTP request sent
'''
def sendMessage(message):
    try:
        # create socket connection and connect to Host URL
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST_URL, PORT))
        # send the GET request through the socket
        sock.sendall(message)
        # set receive message to be empty string
        receive_message = ""
        # receive response from server
        while True:
            answer = str(sock.recv(BUFF_SIZE))
            # if not answer, nothing to receive, break recv loop
            if not answer:
                break
            receive_message += answer
        # close the socket connection
        sock.close()
        # return the String HTML response received
        return receive_message
    # if issue with communication, raise generic error communicating message
    except socket.error:
        raise socket.error("Cannot communicate with server")


'''
Name: run
Parameters: N/A
Use: Driver that runs the program
Return: N/A
'''
def run():
    # get command line args
    arg_len = len(sys.argv)

    # error checks for correct number of command line args
    if arg_len != 3:
        raise ValueError("Insufficient command line arguments")
    # stores first arg as username for login
    username = sys.argv[1]
    # stores second arg as password for login
    password = sys.argv[2]

    # get initial session id and csrf token
    # send initial GET request through the login url and empty csrf token and session id values
    get_message = sendMessage(sendInitialGET(LOGIN_PAGE))
    # gets the csrf token from the HTML data received from the GET request
    csrf = parser(get_message, COOKIE_START)
    # gets the session id from the HTML data received from the GET request
    _init_session = parser(get_message, SESSION_START)

    # login to Fakebook
    post_message = sendMessage(login(LOGIN_PAGE, csrf, _init_session, username, password))
    # gets the session id from the HTML data received from the POST request
    _session = parser(post_message, SESSION_START)

    # if the original session id and session id from POST are the same, there was an error
    # with the login info, raise ValueError indicating incorrect username or password
    if _init_session == _session:
        raise ValueError("Incorrect username or password")

    # iterate through pages
    # start with first page
    pages.append(START_PAGE)
    # while there are pages still to be visited
    while pages:
        # get next page to visit
        page = pages.pop()
        # if have not already visited that page, visit it
        if page not in visited:
            # send GET request with new page to visit
            html_message = sendMessage(sendGET(page, csrf, _session))

            # get the message status
            lines = html_message.split('\n')
            # if status not in first line, iterate until status
            # is found
            line_index = 0
            first = ''
            while line_index < len(lines) and 'HTTP' not in first:
                first = lines[line_index]
                line_index += 1
            # check status message
            # if 301 returned in response, look for location page and append if not
            # visited or in pages
            if '301' in first:
                # try to parse location
                try:
                    location = parser(html_message, LOCATION_START)
                # if no location found, continue search
                except ValueError:
                    continue
                if location not in pages and location not in visited:
                    pages.append(location)
                continue
            # if 403 or 404, page is forbidden or not found
            # append page to visited to prevent revisiting page
            elif '403' in first or '404' in first:
                visited.append(page)
                continue
            # if 500, retry page, append to back of stack
            elif '500' in first:
                pages.append(page)
                continue
            elif '200' not in first:
                raise socket.error("Unknown status error: " + first)
            # parse the HTML data received
            parser(html_message, 'statusCode')
            # append page just visited to visited array
            visited.append(page)

    # print the flags and store them in secret_flags file
    for flag in flags:
        print(flag)


if __name__ == "__main__":
    try:
        run()
    except ValueError as error:
        print(error)
    except IndexError as error:
        print(error)
    except socket.error as error:
        print(error)
