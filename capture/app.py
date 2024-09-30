from flask import Flask, render_template, g
import sqlite3

app = Flask(__name__)
DATABASE = 'requests.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    db = get_db()
    cur = db.cursor()
    cur.execute('''
        SELECT r.id, r.timestamp, r.method, r.uri, r.headers, substr(r.body, 1, 100) as request_body,
               res.status_code, res.reason, res.headers as response_headers, substr(res.body, 1, 100) as response_body
        FROM requests r
        LEFT JOIN responses res ON r.id = res.request_id
        ORDER BY r.timestamp DESC
        LIMIT 100
    ''')
    requests = cur.fetchall()
    return render_template('index.html', requests=requests)

@app.route('/request/<int:request_id>')
def request_detail(request_id):
    db = get_db()
    cur = db.cursor()
    cur.execute('''
        SELECT r.id, r.timestamp, r.src_ip, r.src_port, r.dest_ip, r.dest_port, r.method, r.uri, r.headers, r.body,
               res.status_code, res.reason, res.headers as response_headers, res.body as response_body
        FROM requests r
        LEFT JOIN responses res ON r.id = res.request_id
        WHERE r.id = ?
    ''', (request_id,))
    request = cur.fetchone()
    if request:
        return render_template('request_detail.html', request=request)
    else:
        return 'Request not found', 404

if __name__ == '__main__':
    app.run(debug=True)

