#!/usr/bin/env python3
"""
Ship Proxy Client
Runs on the ship, accepts HTTP proxy connections and forwards them
sequentially over a single TCP connection to the offshore proxy.
"""

import socket
import threading
import logging
import queue
import time
import argparse
import sys
import signal
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import io

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RequestResponse:
    """Container for request/response data"""
    def __init__(self, handler, method, path, headers, body):
        self.handler = handler
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body
        self.response_event = threading.Event()
        self.response_data = None
        self.error = None

class ShipProxy:
    def __init__(self, offshore_host, offshore_port=9999, listen_port=8080):
        self.offshore_host = offshore_host
        self.offshore_port = offshore_port
        self.listen_port = listen_port
        self.running = True
        self.request_queue = queue.Queue()
        self.tcp_socket = None
        self.tcp_lock = threading.Lock()
        self.reconnect_event = threading.Event()
        
    def send_message(self, sock, msg_type, payload):
        """Send a framed message over TCP"""
        try:
            length = len(payload)
            header = length.to_bytes(4, 'big') + msg_type.to_bytes(1, 'big')
            sock.sendall(header + payload)
            logger.debug(f"Sent message: type={msg_type}, length={length}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise
    
    def read_message(self, sock):
        """Read a framed message from TCP"""
        try:
            # Read header (5 bytes)
            header = b''
            while len(header) < 5:
                chunk = sock.recv(5 - len(header))
                if not chunk:
                    raise ConnectionError("Connection closed while reading header")
                header += chunk
            
            length = int.from_bytes(header[:4], 'big')
            msg_type = header[4]
            
            # Read payload
            payload = b''
            while len(payload) < length:
                chunk = sock.recv(length - len(payload))
                if not chunk:
                    raise ConnectionError("Connection closed while reading payload")
                payload += chunk
            
            logger.debug(f"Received message: type={msg_type}, length={length}")
            return msg_type, payload
        except Exception as e:
            logger.error(f"Error reading message: {e}")
            raise
    
    def connect_to_offshore(self):
        """Establish connection to offshore proxy"""
        max_retries = 5
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to offshore proxy at {self.offshore_host}:{self.offshore_port} (attempt {attempt + 1})")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10)
                sock.connect((self.offshore_host, self.offshore_port))
                logger.info("Connected to offshore proxy")
                return sock
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
        
        raise ConnectionError("Failed to connect to offshore proxy after multiple attempts")
    
    def process_request_queue(self):
        """Process queued requests sequentially"""
        logger.info("Started request queue processor")
        
        while self.running:
            try:
                # Get TCP connection
                if self.tcp_socket is None:
                    try:
                        self.tcp_socket = self.connect_to_offshore()
                    except Exception as e:
                        logger.error(f"Failed to establish connection: {e}")
                        time.sleep(5)
                        continue
                
                # Wait for request
                try:
                    req_resp = self.request_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                try:
                    with self.tcp_lock:
                        # Build HTTP request
                        request_data = self.build_http_request(req_resp)
                        
                        # Send request
                        self.send_message(self.tcp_socket, 0, request_data)
                        
                        # Handle CONNECT method specially
                        if req_resp.method == 'CONNECT':
                            # For CONNECT, we need to handle tunneling
                            msg_type, response_data = self.read_message(self.tcp_socket)
                            req_resp.response_data = response_data
                            req_resp.response_event.set()
                            
                            # Start tunneling
                            if b"200 Connection Established" in response_data:
                                self.handle_connect_tunnel(req_resp.handler, self.tcp_socket)
                            continue
                        else:
                            # Read response
                            msg_type, response_data = self.read_message(self.tcp_socket)
                            req_resp.response_data = response_data
                            req_resp.response_event.set()
                            
                except Exception as e:
                    logger.error(f"Error processing request: {e}")
                    req_resp.error = str(e)
                    req_resp.response_event.set()
                    
                    # Reset connection on error
                    if self.tcp_socket:
                        try:
                            self.tcp_socket.close()
                        except:
                            pass
                        self.tcp_socket = None
                
            except Exception as e:
                logger.error(f"Error in request processor: {e}")
                time.sleep(1)
    
    def build_http_request(self, req_resp):
        """Build raw HTTP request bytes"""
        # Request line
        request_line = f"{req_resp.method} {req_resp.path} HTTP/1.1\r\n"
        
        # Headers
        headers_str = ""
        for key, value in req_resp.headers.items():
            headers_str += f"{key}: {value}\r\n"
        
        # Build complete request
        request_str = request_line + headers_str + "\r\n"
        request_bytes = request_str.encode('utf-8') + req_resp.body
        
        return request_bytes
    
    def handle_connect_tunnel(self, handler, tcp_socket):
        """Handle HTTPS tunnel after CONNECT"""
        try:
            # Start bidirectional data relay
            def relay_client_to_server():
                try:
                    while True:
                        data = handler.connection.recv(4096)
                        if not data:
                            break
                        tcp_socket.sendall(data)
                except:
                    pass
            
            def relay_server_to_client():
                try:
                    while True:
                        data = tcp_socket.recv(4096)
                        if not data:
                            break
                        handler.connection.sendall(data)
                except:
                    pass
            
            thread1 = threading.Thread(target=relay_client_to_server)
            thread2 = threading.Thread(target=relay_server_to_client)
            
            thread1.daemon = True
            thread2.daemon = True
            
            thread1.start()
            thread2.start()
            
            thread1.join()
            thread2.join()
            
        except Exception as e:
            logger.error(f"Error in tunnel: {e}")
        finally:
            # Mark TCP socket as unusable after tunnel
            self.tcp_socket = None
    
    def start_queue_processor(self):
        """Start the queue processor thread"""
        processor_thread = threading.Thread(target=self.process_request_queue)
        processor_thread.daemon = True
        processor_thread.start()
        return processor_thread

class ProxyHandler(BaseHTTPRequestHandler):
    """HTTP proxy request handler"""
    
    def __init__(self, ship_proxy, *args, **kwargs):
        self.ship_proxy = ship_proxy
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info(f"{self.address_string()} - {format % args}")
    
    def do_GET(self):
        self.handle_request()
    
    def do_POST(self):
        self.handle_request()
    
    def do_PUT(self):
        self.handle_request()
    
    def do_DELETE(self):
        self.handle_request()
    
    def do_HEAD(self):
        self.handle_request()
    
    def do_OPTIONS(self):
        self.handle_request()
    
    def do_CONNECT(self):
        self.handle_request()
    
    def handle_request(self):
        """Handle any HTTP request"""
        try:
            # Read request body if present
            content_length = int(self.headers.get('Content-Length', 0))
            body = b''
            if content_length > 0:
                body = self.rfile.read(content_length)
            
            # Create request/response container
            req_resp = RequestResponse(
                handler=self,
                method=self.command,
                path=self.path,
                headers=dict(self.headers),
                body=body
            )
            
            logger.info(f"Queuing {self.command} request to {self.path}")
            
            # Queue the request
            self.ship_proxy.request_queue.put(req_resp)
            
            # Wait for response
            req_resp.response_event.wait(timeout=60)  # 60 second timeout
            
            if req_resp.error:
                logger.error(f"Request failed: {req_resp.error}")
                self.send_error(502, "Bad Gateway")
                return
            
            if req_resp.response_data is None:
                logger.error("Request timeout")
                self.send_error(504, "Gateway Timeout")
                return
            
            # For CONNECT, just send the response and let tunneling handle the rest
            if self.command == 'CONNECT':
                self.connection.sendall(req_resp.response_data)
                return
            
            # Send response back to client
            self.connection.sendall(req_resp.response_data)
            
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            try:
                self.send_error(500, "Internal Server Error")
            except:
                pass

def create_handler(ship_proxy):
    """Create handler class with ship_proxy reference"""
    class BoundProxyHandler(ProxyHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(ship_proxy, *args, **kwargs)
    return BoundProxyHandler

def main():
    parser = argparse.ArgumentParser(description='Ship Proxy Client')
    parser.add_argument('--offshore-host', required=True, help='Offshore proxy host')
    parser.add_argument('--offshore-port', type=int, default=9999, help='Offshore proxy port')
    parser.add_argument('--listen-port', type=int, default=8080, help='Local proxy listen port')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create ship proxy
    ship_proxy = ShipProxy(args.offshore_host, args.offshore_port, args.listen_port)
    
    # Start queue processor
    processor_thread = ship_proxy.start_queue_processor()
    
    # Create HTTP server
    handler_class = create_handler(ship_proxy)
    httpd = HTTPServer(('0.0.0.0', args.listen_port), handler_class)
    
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal")
        ship_proxy.running = False
        httpd.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info(f"Ship proxy listening on port {args.listen_port}")
    logger.info(f"Forwarding to offshore proxy at {args.offshore_host}:{args.offshore_port}")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    main()