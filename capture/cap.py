from scapy.all import *
import sqlite3
import time
import zlib

def main():
    # Open SQLite database
    conn = sqlite3.connect('requests.db')
    c = conn.cursor()
    # Create tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            src_ip TEXT,
            src_port INTEGER,
            dest_ip TEXT,
            dest_port INTEGER,
            method TEXT,
            uri TEXT,
            headers TEXT,
            body TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            timestamp REAL,
            status_code INTEGER,
            reason TEXT,
            headers TEXT,
            body BLOB,
            FOREIGN KEY(request_id) REFERENCES requests(id)
        )
    ''')
    conn.commit()

    # Filter for traffic to and from 192.168.4.152 on port 11000
    filter_str = 'tcp port 11000 and host 192.168.4.152'

    # Dictionary to hold TCP streams and their associated data
    streams = {}

    def packet_handler(packet):
        if packet.haslayer(TCP) and packet.haslayer(Raw):
            ip_layer = packet.getlayer(IP)
            tcp_layer = packet.getlayer(TCP)
            raw_data = bytes(packet.getlayer(Raw).load)

            src_ip = ip_layer.src
            dst_ip = ip_layer.dst
            src_port = tcp_layer.sport
            dst_port = tcp_layer.dport

            # Identify stream by tuple (client_ip, client_port, server_ip, server_port)
            if tcp_layer.dport == 11000:
                # Traffic from client to server (request)
                stream_id = (src_ip, src_port, dst_ip, dst_port)
                direction = 'request'
            else:
                # Traffic from server to client (response)
                stream_id = (dst_ip, dst_port, src_ip, src_port)
                direction = 'response'

            # Initialize stream if not exists
            if stream_id not in streams:
                streams[stream_id] = {
                    'client_data': b'',
                    'server_data': b'',
                    'request_id': None,
                    'last_activity': time.time()
                }

            # Update last activity time
            streams[stream_id]['last_activity'] = time.time()

            # Append data to stream
            if direction == 'request':
                streams[stream_id]['client_data'] += raw_data
            else:
                streams[stream_id]['server_data'] += raw_data

            # Process request and response
            process_stream(stream_id, streams[stream_id], c, conn)

            # Clean up old streams (optional)
            cleanup_streams(streams)

    def process_stream(stream_id, stream_data, cursor, conn):
        # Process client data (requests)
        client_data = stream_data['client_data']
        while True:
            # Look for end of headers
            request_end = client_data.find(b'\r\n\r\n')
            if request_end == -1:
                # Not a complete request yet
                break
            request_end += 4  # Include the length of '\r\n\r\n'
            request_data = client_data[:request_end].decode('utf-8', 'ignore')
            body = client_data[request_end:]

            # Parse request line
            lines = request_data.split('\r\n')
            request_line = lines[0]
            try:
                method, uri, version = request_line.split(' ')
            except ValueError:
                # Invalid request line
                method, uri, version = '', '', ''
            print(f"Method: {method}, URI: {uri}, Version: {version}")
            headers = '\r\n'.join(lines[1:])

            # Get Content-Length if available
            content_length = 0
            for line in lines[1:]:
                if line.lower().startswith('content-length'):
                    content_length = int(line.split(':')[1].strip())
                    break

            # Read the body based on Content-Length
            if len(body) < content_length:
                # Wait for more data
                break
            else:
                body_data = body[:content_length]
                remaining_data = body[content_length:]

            # Store in database
            cursor.execute('''
                INSERT INTO requests (timestamp, src_ip, src_port, dest_ip, dest_port, method, uri, headers, body)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (time.time(), stream_id[0], stream_id[1], stream_id[2], stream_id[3], method, uri, headers, body_data.decode('utf-8', 'ignore')))
            conn.commit()
            request_id = cursor.lastrowid

            # Update the stream data with new request_id
            stream_data['request_id'] = request_id

            # Remove processed data
            client_data = remaining_data
            stream_data['client_data'] = client_data

        # Process server data (responses)
        server_data = stream_data['server_data']
        while True:
            # Look for end of headers
            response_end = server_data.find(b'\r\n\r\n')
            if response_end == -1:
                # Not a complete response yet
                break
            response_end += 4  # Include the length of '\r\n\r\n'
            response_data = server_data[:response_end].decode('utf-8', 'ignore')
            body = server_data[response_end:]

            # Parse status line
            lines = response_data.split('\r\n')
            status_line = lines[0]
            try:
                version, status_code, reason_phrase = status_line.split(' ', 2)
            except ValueError:
                # Invalid status line
                version, status_code, reason_phrase = '', '', ''
            headers = '\r\n'.join(lines[1:])

            # Get Content-Length if available
            content_length = 0
            for line in lines[1:]:
                if line.lower().startswith('content-length'):
                    content_length = int(line.split(':')[1].strip())
                    break

            # Read the body based on Content-Length
            if len(body) < content_length:
                # Wait for more data
                break
            else:
                body_data = body[:content_length]
                remaining_data = body[content_length:]

            # Handle gzip content if necessary
            if 'Content-Encoding: gzip' in headers:
                try:
                    body_data = zlib.decompress(body_data, zlib.MAX_WBITS | 16)
                except Exception as e:
                    print('Error decompressing gzipped content:', e)

            # Store in database
            cursor.execute('''
                INSERT INTO responses (request_id, timestamp, status_code, reason, headers, body)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (stream_data['request_id'], time.time(), status_code, reason_phrase, headers, body_data))
            conn.commit()

            # Remove processed data
            server_data = remaining_data
            stream_data['server_data'] = server_data

            # Reset request_id if HTTP/1.0 without Keep-Alive
            if 'Connection: close' in headers or 'Connection: Close' in headers:
                stream_data['request_id'] = None

    def cleanup_streams(streams):
        # Remove streams that have been inactive for more than 300 seconds
        current_time = time.time()
        inactive_streams = [stream_id for stream_id, data in streams.items() if current_time - data['last_activity'] > 300]
        for stream_id in inactive_streams:
            del streams[stream_id]

    # Start sniffing
    sniff(filter=filter_str, prn=packet_handler, store=False)

if __name__ == '__main__':
    main()

