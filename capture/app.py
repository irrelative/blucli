from flask import Flask, render_template, g, url_for
import sqlite3

app = Flask(__name__)
DATABASE = 'requests.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        # Ensure that row_factory is set to sqlite3.Row for easy access
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
        SELECT r.id, r.timestamp, r.method, r.uri, r.headers, substr(r.body, 1, 100) as body
        FROM requests r
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
        SELECT id, timestamp, src_ip, src_port, dest_ip, dest_port, method, uri, headers, body
        FROM requests
        WHERE id = ?
    ''', (request_id,))
    request = cur.fetchone()
    if request:
        return render_template('request_detail.html', request=request)
    else:
        return 'Request not found', 404

@app.route('/responses')
def responses():
    db = get_db()
    cur = db.cursor()
    cur.execute('''
        SELECT id, timestamp, status_code, reason, headers, substr(body, 1, 100) as body
        FROM responses
        ORDER BY timestamp DESC
        LIMIT 100
    ''')
    responses = cur.fetchall()
    return render_template('responses.html', responses=responses)

@app.route('/response/<int:response_id>')
def response_detail(response_id):
    db = get_db()
    cur = db.cursor()
    cur.execute('''
        SELECT id, timestamp, status_code, reason, headers, body
        FROM responses
        WHERE id = ?
    ''', (response_id,))
    response = cur.fetchone()
    if response:
        return render_template('response_detail.html', response=response)
    else:
        return 'Response not found', 404

if __name__ == '__main__':
    app.run(debug=True)

