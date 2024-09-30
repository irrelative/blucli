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
            timestamp REAL,
            status_code INTEGER,
            reason TEXT,
            headers TEXT,
            body BLOB
        )
    ''')
    conn.commit()

    # Filter for traffic to and from 192.168.4.152 on port 11000
    filter_str = 'tcp port 11000 and host 192.168.4.152'

    # Dictionary to hold TCP streams
    streams = {}

    def packet_handler(packet):
        if packet.haslayer(TCP) and packet.haslayer(Raw):
            ip_layer = packet.getlayer(IP)
            tcp_layer = packet.getlayer(TCP)
            raw_data = packet.getlayer(Raw).load

            src_ip = ip_layer.src
            dst_ip = ip_layer.dst
            src_port = tcp_layer.sport
            dst_port = tcp_layer.dport

            # Identify stream by tuple
            if tcp_layer.dport == 11000:
                stream_id = (src_ip, src_port, dst_ip, dst_port)
            else:
                stream_id = (dst_ip, dst_port, src_ip, src_port)

            # Initialize stream if not exists
            if stream_id not in streams:
                streams[stream_id] = b''

            # Append data to stream
            streams[stream_id] += raw_data

            # Attempt to parse HTTP messages
            data = streams[stream_id]
            try:
                # Check if data starts with HTTP request
                if data.startswith((b'GET', b'POST', b'PUT', b'DELETE', b'OPTIONS', b'HEAD', b'PATCH')):
                    request_end = data.find(b'\r\n\r\n')
                    if request_end == -1:
                        # Not a complete request yet
                        return
                    request_end += 4
                    request_data = data[:request_end].decode('utf-8', 'ignore')
                    body = data[request_end:]

                    # Parse request line
                    lines = request_data.split('\r\n')
                    request_line = lines[0]
                    try:
                        method, uri, version = request_line.split(' ')
                    except ValueError:
                        # Invalid request line
                        method, uri, version = '', '', ''
                    headers = '\r\n'.join(lines[1:])

                    # For simplicity, assume the body is any remaining data
                    # In production, handle Content-Length and Transfer-Encoding properly

                    # Store in database
                    c.execute('''
                        INSERT INTO requests (timestamp, src_ip, src_port, dest_ip, dest_port, method, uri, headers, body)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (time.time(), src_ip, src_port, dst_ip, dst_port, method, uri, headers, body.decode('utf-8', 'ignore')))
                    conn.commit()
                    # Remove processed data
                    streams[stream_id] = data[request_end + len(body):]
                # Check if data starts with HTTP response
                elif data.startswith(b'HTTP/'):
                    response_end = data.find(b'\r\n\r\n')
                    if response_end == -1:
                        # Not a complete response yet
                        return
                    response_end += 4
                    response_data = data[:response_end].decode('utf-8', 'ignore')
                    body = data[response_end:]

                    # Parse status line
                    lines = response_data.split('\r\n')
                    status_line = lines[0]
                    try:
                        version, status_code, reason_phrase = status_line.split(' ', 2)
                    except ValueError:
                        # Invalid status line
                        version, status_code, reason_phrase = '', '', ''
                    headers = '\r\n'.join(lines[1:])

                    # Handle gzip content if necessary
                    if 'Content-Encoding: gzip' in headers:
                        try:
                            body = zlib.decompress(body, zlib.MAX_WBITS|16)
                        except Exception as e:
                            print('Error decompressing gzipped content:', e)

                    # Store in database
                    c.execute('''
                        INSERT INTO responses (timestamp, status_code, reason, headers, body)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (time.time(), status_code, reason_phrase, headers, body))
                    conn.commit()
                    # Remove processed data
                    streams[stream_id] = data[response_end + len(body):]
                else:
                    # Not enough data yet or unrecognized data
                    pass
            except Exception as e:
                print('Error parsing HTTP data:', e)
                # Remove stream to prevent infinite loop
                del streams[stream_id]

    # Start sniffing
    sniff(filter=filter_str, prn=packet_handler, store=False)

if __name__ == '__main__':
    main()

