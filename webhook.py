from flask import Flask, request, Response, render_template, redirect, url_for
import hmac
import hashlib
from datetime import datetime
import sqlite3
import json

app = Flask(__name__, static_url_path='/static')


def init_db():
    with sqlite3.connect('webhooks.db') as conn:
        conn.execute('''
        CREATE TABLE IF NOT EXISTS webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            secret TEXT NOT NULL,
            description TEXT,
            endpoint TEXT UNIQUE NOT NULL
        )
        ''')

        conn.execute('''
        CREATE TABLE IF NOT EXISTS webhook_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            webhook_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT,
            payload JSON,
            status_code INTEGER,
            FOREIGN KEY (webhook_id) REFERENCES webhooks (id)
        )
        ''')
        conn.commit()


def get_db():
    conn = sqlite3.connect('webhooks.db')
    conn.row_factory = sqlite3.Row
    return conn


def get_webhooks():
    with get_db() as conn:
        webhooks = conn.execute('SELECT * FROM webhooks').fetchall()
        result = {}
        for webhook in webhooks:
            # Get recent calls for this webhook
            calls = conn.execute('''
                SELECT * FROM webhook_calls 
                WHERE webhook_id = ? 
                ORDER BY timestamp DESC LIMIT 100
            ''', (webhook['id'],)).fetchall()

            # Convert calls to list of dictionaries
            calls_list = []
            for call in calls:
                calls_list.append({
                    'timestamp': call['timestamp'],
                    'event_type': call['event_type'],
                    'payload': json.loads(call['payload']) if call['payload'] else {},
                    'status_code': call['status_code']
                })

            result[webhook['name']] = {
                'id': webhook['id'],
                'secret': webhook['secret'],
                'description': webhook['description'],
                'endpoint': webhook['endpoint'],
                'calls': calls_list
            }
        return result


@app.route('/')
def index():
    webhooks = get_webhooks()
    return render_template('index.html', webhooks=webhooks)


@app.route('/add_webhook', methods=['POST'])
def add_webhook():
    name = request.form.get('name')
    secret = request.form.get('secret')
    description = request.form.get('description')
    endpoint = request.form.get('endpoint')

    if name and secret and endpoint:
        try:
            with get_db() as conn:
                conn.execute('''
                    INSERT INTO webhooks (name, secret, description, endpoint)
                    VALUES (?, ?, ?, ?)
                ''', (name, secret, description, endpoint))
                conn.commit()
        except sqlite3.IntegrityError:
            # Handle duplicate name or endpoint
            pass
    return redirect(url_for('index'))


@app.route('/update_webhook', methods=['POST'])
def update_webhook():
    name = request.form.get('name')
    secret = request.form.get('secret')
    description = request.form.get('description')

    if name and secret:
        with get_db() as conn:
            conn.execute('''
                UPDATE webhooks 
                SET secret = ?, description = ?
                WHERE name = ?
            ''', (secret, description, name))
            conn.commit()
    return redirect(url_for('index'))


@app.route('/webhook/<endpoint>', methods=['POST'])
def webhook(endpoint):
    with get_db() as conn:
        # Get webhook configuration
        webhook = conn.execute('''
            SELECT * FROM webhooks WHERE endpoint = ?
        ''', (endpoint,)).fetchone()

        if not webhook:
            return Response('Webhook not found', status=404)

        event_type = request.headers.get('X-GitHub-Event', 'unknown')
        payload = request.get_json() if request.is_json else {}

        # Store the webhook call
        conn.execute('''
            INSERT INTO webhook_calls 
            (webhook_id, event_type, payload, status_code)
            VALUES (?, ?, ?, ?)
        ''', (webhook['id'], event_type, json.dumps(payload), 200))
        conn.commit()

        return Response(f'Event received for webhook: {webhook["name"]}', status=200)


@app.route('/delete_webhook/<name>', methods=['POST'])
def delete_webhook(name):
    with get_db() as conn:
        # First delete related calls
        webhook = conn.execute('SELECT id FROM webhooks WHERE name = ?', (name,)).fetchone()
        if webhook:
            conn.execute('DELETE FROM webhook_calls WHERE webhook_id = ?', (webhook['id'],))
            conn.execute('DELETE FROM webhooks WHERE name = ?', (name,))
            conn.commit()
    return redirect(url_for('index'))


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=3000, debug=True)