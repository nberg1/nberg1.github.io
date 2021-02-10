# CS5700_project2
Web Crawler for project 2 in cs5700 Network Fundamentals

In this file, you should briefly describe your high-level approach,
any challenges you faced, and an overview of how you tested your code.
You must also include a detailed description of which student worked on
which part of the code.

For this project, the first thing we approached was the problem of connecting
to the server. To do this, we first read the provided literature "HTTP Made
Really Easy" and conducted independent research online regarding formatting
HTTP GET and POST posts. We then used the developer tools in Google Chrome
to determine the requests that the browser was making to the server and the
responses the server returned to the browser. Using the information we gathered
from these three sources, we determined how to retrieve the session id, crsf token,
and the headers necessary to illicit a response from the server.

Once we were able to communicate with the server, we used the responses we received
to create an html parser in order to retrieve page references, secret flags, and
the session id and csrf tokens necessary for continuing the search, completing
the search, and gaining access to the website, respectively. Once we were able
to parse the necessary information, we utilized an iterative depth-first-search
with a 'pages' stack that held pages to be visited in order to to crawl the website.
Pages that were visited were added to another list called 'visited' - this ensured
that pages that had been visited would not be visited twice in order to
prevent the website from "ping-ponging" between pages.

When handling messages from the server, if a 403 or 404 status message was
returned, we added the page to the 'visited' list so it would not be added
when pulling references from html available on other pages that were being
evaluated. If a 500 status message was returned, the page reference was appended
to the stack of pages to be searched as the next page in the crawl. If a 301
status message was returned, we parsed for the 'Location' header in the message,
and if not location was found, we continued the search since the rest of the website
could still be crawled so long as there were more pages in the stack. If a 200
status was not returned, a socket error was raised indicating the error that
was raised. Since we do not have instructions on how to handle this error,
it stops the program as it may be fatal.

As for the division of work, Joe designed the GET and POST messages, designed
the DFS with the stack, handled getting command line arguments,
handled finding and handling status errors, and created this README text file.
Nicole, (brilliantly) constructed  the login string for the POST message, found
and implemented the HTMLParser library to find references, flags, session id
and crsf tokens, refactored the code to consolidate GET and POST message
generation to be sent over the socket to the server, documented the code, and
created the Makefile.

Our greatest challenge was in communicating with the server. We were both new
to HTTP protocol, and spent a great deal of time figuring out how to communicate
with the server. Eventually, after meticulously reviewing HTTP protocols in
the aforementioned literature and our online research and examining the
requests and headers with developer tools, we discovered that we needed to
get a csrf token and session id from the login page, and then use those cookies
to POST a message to the login page and get the session id we needed in order
to crawl the rest of the website. After that, the parser provided some difficulty
as did managing which pages had been visited and which pages left Fakebook so the
crawler would not leave the website, though these problems were solved in a few
hours. We experimented with both HTTP/1.1 and HTTP/1.0 protocols, but our experience
was that the 1.0 ran faster on the Khoury servers, and thus elected to use this version.
Both versions worked well, but, using the time library, we found that the 1.0 version
ran in under half the time as our 1.1 version. We continue to investigate the reason
for this in our own time.

For testing, when communicating with the server it was primarily trial and error.
We would devise a GET message, send the message over the server, and use the
response (if we got one) to try and understand where our code went wrong until
we received a 200 status. We used a similar methodology until we received a good
response from the login POST message and subsequent GET messages for crawling
the website. For parsing the messages returned from the server, we took the
good messages we returned, saved them as a string, and then used the strings
to develop a good parser. We used a similar method to check for status codes
in the messages and make sure we were catching the right statuses so we could
take the appropriate action. Since we were new to the HTTP protocol, we figured
the best way to learn how to parse and handle these messages was to use real
messages from the server. By understanding how the messages returned from the
server would be formatted, it made it much easier to parse references, flags,
session id and csrf tokens, and how to deal with HTTP protocols in general.