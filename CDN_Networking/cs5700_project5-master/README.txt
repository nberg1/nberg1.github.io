Final Submission
Project 5
Joe Burns and Nicole Berg

README

We developed our project in increments, with the first phase of our implementation focusing on developing the DNS
and HTTP replica servers. We then focused on deployment, developing a method of scp-ing scripts into the replica servers
and then ssh-ing into each replica server to pre-fetch the local cache. Then we worked on our stopCDN script, which not
only terminated the program, but also cleaned the replica servers and dns server such that each location appeared
as it did prior to deployment. Last we worked on the runCDN script, which posed a challenge as executing the run command
from the command line required that the program could run in the background and not in the shell where it was called.

Our program implemented geolocation and active measurements to find the optimal replica server for each client. We
also implemented multithreading in an attempt to serve multiple clients at each replica server and to optimize
server deployment, running the servers, and shutting the servers down. We also used multithreading to
request active measurements from the DNS server to the replica servers so that the DNS server could continue to
server DNS requests while replica-to-client RTT mappings were updated.

To provide as many cache-hits as possible, we used the gzip library to compress our resources during pre-fetching in
deployment, choosing those resources that were most popular according to the Zipf distribution described in the provided
csv file.

Developing the DNS server with the DNS library was fairly difficult, though by looking at the public Github repo,
following what documentation was available, and scouring online resources posted by other programmers using the library,
we managed to get it in good working order. Testing runtimes for tasks such as getting active measurements, unzipping
content, prefetching, and turning around DNS/HTTP queries was also tricky, though well placed time.time() calls would
reveal what optimizations provided the most consistent and fastest methods.

Report

For our CDN, we implemented active measurements as well as finding geo-locations of IP addresses to direct clients to
their fastest or closest replica server. Our DNS server was responsible for keeping track of where to send IP addresses.

Initially, upon a client’s first request to the server, the DNS server directed the client to the closest server to the
client, which was determined using longitude and latitude based on what was returned from the IP address geolocation
database and comparing it to the longitude and latitude of stored EC2 IP addresses. This information was then stored
such that if the client made another request to the server, the DNS server could direct the client to their closest
replica server without re-querying the database and running the calculation to determine distance again.

The DNS server would also collect client IPs and periodically send requests to all replica servers to
determine the RTT to the closest public IP address found on a traceroute to a client IP address. The replica servers
would then return the results of these findings, and the DNS server would determine which replica server provided the
lowest RTT to each client IP address and associate that replica server with the client such that each subsequent time
client sent a request to the DNS server, the DNS could return the replica server with the lowest RTT to the client.
Once RTT values for a client IP address had been found, the replica server with the lowest RTT to the client was given
priority over the closest replica server geographically, thus relying more heavily on active measurements than
geolocations.

To make active measurements requests from the DNS server, we connected to each replica server via the socket on which
client’s requests are directed, thus utilizing existing functionality used to serve client requests. We then
crafted a GET request and provided a special DNS key used to identify an active measurement request from the server,
thereby differentiating it from client requests. Similar to client requests, these measurements were conducted in a
separate thread, which allows the server to continue serving requests while the replica server is probing RTTs for
client IPs.

To implement active measurements, we used information about client IPs from the given beacons (addresses and their
closest geographical IP address) and conducted manual traceroutes and pings from the command line with Scamper.
This is how we discovered that there are multiple hops in a traceroute over private or reserved IP addresses that
cannot be pinged. This led us to work backwards through the results of the traceroute to find the closest public IP
address to the client and then ping that address as opposed to pinging simply the closest (and possibly private) IP.
However, we did run into an issue where some public IPs experienced 100% packet loss upon being pinged, though we were also
concerned that if we went too far back in a traceroute, we would find ourselves too far from the client IP to have an
accurate measurement of the RTT from the replica server to the client. While we did want results from a good ping for
all replica-to-client IP traceroutes, moving too far up the traceroute from the client IP increases the chances that
something could happen to the connection between the last good public IP and the client. Thus, we were faced with a
difficult choice: rely on good pings at the cost of relevance and execution time, or use the RTT from the traceroute
itself at the cost off accuracy. In the end, we decided that if we came across a public IP that experienced complete
packet loss when pinged, we would use the RTT provided from the traceroute itself. While this information is not as
reliable as the results of a good ping, we found that the RTT values gathered during the traceroute were generally in
line with that of what was returned from successful pings based on empirical data gathered when conducting manual
experiments with scamper. Additionally, our program updates these values approximately every thirty seconds, so any
bad information would be fairly short-lived.

Upon deployment on our servers, we chose to pre-fetch the top 125 most popular pages from the server and store
them in a local cache, using the gzip library to compress files and save space at the replica servers. Originally,
we intended to leave these files un-compressed, as we believed unzipping their contents would take precious additional
time to turning around a query. Surprisingly, we found that decompressing files with gzip ran as fast and sometimes even
faster than fetching the plain-text. While this normally would have taken a great deal of time, by implementing
multithreading to fetch each resource from the origin concurrently, we were able to pre-fetch all 125 resources at
each replica server in under 30 seconds.

We also made the decision to pre-fetch the geolocation IP database from MaxMind (who authored the geoip2 library) at
the time of deployment. Choosing to dynamically download this each time the DNS and replica servers were deployed
ensured that we had the most up-to-date version of the database, and thus provided the most accurate geolocation
measurements possible.

Additionally, we implemented multithreading at the replica servers such that each time our replica server received a
request, the program could relegate fulfilling that request to its own thread with the socket object spawned by the
socket.accept() method. This also prevented blocking when receiving requests from multiple clients. However, we ran
into difficulties implementing this same functionality in our DNS servers since we used the DNSPython receive_udp and
send_udp methods, which operate on a single udp socket. Because of this, we can only serve a single dns request at a
time. This concern is mitigated somewhat by our DNS server’s ability to return stored information after a client’s
initial request in constant time, regardless of whether the returned value corresponds to a stored geolocation or
active measurement.

All measurements of optimization techniques were developed using enclosing time.time() calls from the time library
which would be printed to the screen immediately before an action was taken and as soon as that action finished.
This helped us visually confirm that our design choices were providing sufficient speedups despite increased
complexity in our program. We also used the "time" call before digs and wgets from our local machines to determine
the overall runtime for DNS queries and content requests to replica servers.

Given more time to complete the assignment, we would like to have pursued passive measurements to gather more accurate
information regarding RTTs between clients and the replica IPs to which they were directed. Gathering and storing
client IPs upon receiving a request at the replica server was easy enough, and we devised a strategy to inject this
information into what is returned to the DNS server during an active measurement request, a strategy which also would
have reduced the total number of active measurements performed by the number of passive measurements provided at the
replica server. This would have also provided us good information about the accuracy of our active measurements.
However, deriving this value while returning requested data to the client proved rather tricky, and while we made
progress on this problem, we were not confident enough in our methods to include it in our final submission nor rely
on our results.

