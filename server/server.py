#!/usr/bin/env python3
"""
Offshore Proxy Server
Runs remotely and receives requests over a single TCP connection from the ship proxy.
Forwards requests to target servers and sends responses back.
"""

import socket
import threading
import logging
import http.client
import ssl
import urllib.parse
import sys
import signal
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OffshoreProxy:
    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port
        self.running = True
        self.server_socket = None
        
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
    
    def parse_http_request(self, request_data):
        """Parse raw HTTP request data"""
        try:
            request_str = request_data.decode('utf-8', errors='ignore')
            lines = request_str.split('\r\n')
            
            if not lines:
                raise ValueError("Empty request")
            
            # Parse request line
            request_line = lines[0]
            parts = request_line.split(' ')
            if len(parts) != 3:
                raise ValueError(f"Invalid request line: {request_line}")
            
            method, url, version = parts
            
            # Parse headers
            headers = {}
            body_start = 1
            for i, line in enumerate(lines[1:], 1):
                if line == '':
                    body_start = i + 1
                    break
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip().lower()] = value.strip()
            
            # Extract body
            body = b''
            if body_start < len(lines):
                body_str = '\r\n'.join(lines[body_start:])
                body = body_str.encode('utf-8')
            
            return method, url, version, headers, body
        except Exception as e:
            logger.error(f"Error parsing HTTP request: {e}")
            raise
    
    def forward_http_request(self, method, url, version, headers, body):
        """Forward HTTP request to target server"""
        try:
            # Parse URL
            if url.startswith('http://') or url.startswith('https://'):
                parsed = urllib.parse.urlparse(url)
                host = parsed.hostname
                port = parsed.port
                path = parsed.path
                if parsed.query:
                    path += '?' + parsed.query
                use_ssl = parsed.scheme == 'https'
                if port is None:
                    port = 443 if use_ssl else 80
            else:
                # Handle proxy requests
                if 'host' in headers:
                    host_header = headers['host']
                    if ':' in host_header:
                        host, port = host_header.split(':')
                        port = int(port)
                    else:
                        host = host_header
                        port = 80
                    path = url
                    use_ssl = False
                else:
                    raise ValueError("Cannot determine target host")
            
            logger.info(f"Forwarding {method} request to {host}:{port}{path}")
            
            # Create connection
            if use_ssl:
                context = ssl.create_default_context()
                conn = http.client.HTTPSConnection(host, port, context=context, timeout=30)
            else:
                conn = http.client.HTTPConnection(host, port, timeout=30)
            
            # Remove hop-by-hop headers
            filtered_headers = {}
            hop_by_hop = ['connection', 'proxy-authenticate', 'proxy-authorization',
                         'te', 'trailers', 'upgrade']
            for key, value in headers.items():
                if key.lower() not in hop_by_hop:
                    filtered_headers[key] = value
            
            # Make request
            conn.request(method, path, body, filtered_headers)
            response = conn.getresponse()
            
            # Read response
            response_data = response.read()
            
            # Build response
            response_line = f"HTTP/1.1 {response.status} {response.reason}\r\n"
            response_headers = ""
            for header, value in response.getheaders():
                response_headers += f"{header}: {value}\r\n"
            
            response_bytes = (response_line + response_headers + "\r\n").encode('utf-8') + response_data
            
            conn.close()
            return response_bytes
            
        except Exception as e:
            logger.error(f"Error forwarding request: {e}")
            # Return error response
            error_response = f"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n"
            return error_response.encode('utf-8')
    
    def handle_connect_request(self, conn, url, headers):
        """Handle HTTPS CONNECT request"""
        try:
            # Parse host and port from URL
            if ':' in url:
                host, port = url.split(':')
                port = int(port)
            else:
                host = url
                port = 443
            
            logger.info(f"Establishing CONNECT tunnel to {host}:{port}")
            
            # Connect to target server
            target_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_sock.settimeout(30)
            target_sock.connect((host, port))
            
            # Send 200 Connection Established
            response = b"HTTP/1.1 200 Connection Established\r\n\r\n"
            self.send_message(conn, 1, response)
            
            # Start bidirectional relay
            def relay_data(src, dst, direction):
                try:
                    while True:
                        data = src.recv(4096)
                        if not data:
                            break
                        dst.sendall(data)
                except:
                    pass
                finally:
                    src.close()
                    dst.close()
            
            # Start relay threads
            thread1 = threading.Thread(target=relay_data, args=(target_sock, conn, "target->client"))
            thread2 = threading.Thread(target=relay_data, args=(conn, target_sock, "client->target"))
            
            thread1.daemon = True
            thread2.daemon = True
            
            thread1.start()
            thread2.start()
            
            # Wait for threads to finish
            thread1.join()
            thread2.join()
            
        except Exception as e:
            logger.error(f"Error handling CONNECT: {e}")
            error_response = b"HTTP/1.1 502 Bad Gateway\r\n\r\n"
            self.send_message(conn, 1, error_response)
    
    def handle_client_connection(self, conn, addr):
        """Handle connection from ship proxy"""
        logger.info(f"Connection established with {addr}")
        
        try:
            while self.running:
                # Read request
                msg_type, request_data = self.read_message(conn)
                
                if msg_type != 0:  # Expect request
                    logger.warning(f"Unexpected message type: {msg_type}")
                    continue
                
                # Parse HTTP request
                try:
                    method, url, version, headers, body = self.parse_http_request(request_data)
                    
                    if method == 'CONNECT':
                        # Handle HTTPS tunneling
                        self.handle_connect_request(conn, url, headers)
                        break  # Connection will be used for tunneling
                    else:
                        # Handle regular HTTP request
                        response_data = self.forward_http_request(method, url, version, headers, body)
                        self.send_message(conn, 1, response_data)
                        
                except Exception as e:
                    logger.error(f"Error processing request: {e}")
                    error_response = b"HTTP/1.1 400 Bad Request\r\n\r\n"
                    self.send_message(conn, 1, error_response)
                    
        except Exception as e:
            logger.error(f"Error in client connection: {e}")
        finally:
            conn.close()
            logger.info(f"Connection closed with {addr}")
    
    def start(self):
        """Start the offshore proxy server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            
            logger.info(f"Offshore proxy server listening on {self.host}:{self.port}")
            
            while self.running:
                try:
                    conn, addr = self.server_socket.accept()
                    thread = threading.Thread(
                        target=self.handle_client_connection,
                        args=(conn, addr)
                    )
                    thread.daemon = True
                    thread.start()
                except socket.error as e:
                    if self.running:
                        logger.error(f"Error accepting connection: {e}")
                    
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()
    
    def stop(self):
        """Stop the server"""
        logger.info("Stopping offshore proxy server...")
        self.running = False
        if self.server_socket:
            self.server_socket.close()

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal")
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start server
    server = OffshoreProxy()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()