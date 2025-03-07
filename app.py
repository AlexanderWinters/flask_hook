from flask import Flask, request, Response
import hmac
import hashlib
import subprocess
import os

app = Flask(__name__)

# REPLACE WITH YOUR SECRET
WEBHOOK_SECRET = 'your-webhook-secret'


def is_valid_signature(payload_body, signature_header):
    if not signature_header:
        return False

    expected_signature = hmac.new(
        key=WEBHOOK_SECRET.encode(),
        msg=payload_body,
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(
        f'sha256={expected_signature}',
        signature_header
    )


def deploy():
    # CHANGE TO CORRECT PATH
    deploy_script = '/path/to/deploy.sh'

    try:
        os.chmod(deploy_script, 0o755)
        result = subprocess.run(
            ['bash', deploy_script],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr

    except Exception as e:
        return False, str(e)


@app.route('/webhook', methods=['POST'])
def webhook():
    signature_header = request.headers.get('X-Hub-Signature-256')

    if not is_valid_signature(request.get_data(), signature_header):
        return Response('Invalid signature', status=403)

    # Parse the JSON payload
    event = request.json

    # Check if it's a push event
    if request.headers.get('X-GitHub-Event') == 'push':
        success, message = deploy()

        if success:
            return Response(f'Deployed successfully: {message}', status=200)
        else:
            return Response(f'Deployment failed: {message}', status=500)

    return Response('Event received but no action taken', status=200)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)