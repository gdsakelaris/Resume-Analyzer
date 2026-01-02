#!/usr/bin/env python3
"""
Simple webhook server for GitHub auto-deployment.
Listens for GitHub push events and triggers deployment script.
"""

import hmac
import hashlib
import subprocess
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

# IMPORTANT: Set this secret in GitHub webhook settings
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', 'your-secret-key-here')
DEPLOY_SCRIPT = '/home/ubuntu/Resume-Analyzer/deploy.sh'


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Only accept POST requests to /webhook
        if self.path != '/webhook':
            self.send_response(404)
            self.end_headers()
            return

        # Read the payload
        content_length = int(self.headers['Content-Length'])
        payload = self.rfile.read(content_length)

        # Verify GitHub signature
        signature = self.headers.get('X-Hub-Signature-256')
        if not self.verify_signature(payload, signature):
            print("Invalid signature - rejecting webhook")
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b'Invalid signature')
            return

        # Parse the payload
        try:
            data = json.loads(payload)
            ref = data.get('ref', '')

            # Only deploy on push to main branch
            if ref == 'refs/heads/main':
                print(f"Received push to main branch - triggering deployment")

                # Run deployment script
                result = subprocess.run(
                    ['bash', DEPLOY_SCRIPT],
                    capture_output=True,
                    text=True
                )

                print("Deployment output:")
                print(result.stdout)

                if result.returncode != 0:
                    print("Deployment failed:")
                    print(result.stderr)
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b'Deployment failed')
                    return

                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'Deployment triggered successfully')
            else:
                print(f"Ignoring push to {ref}")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'Ignored - not main branch')

        except Exception as e:
            print(f"Error processing webhook: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'Internal server error')

    def verify_signature(self, payload, signature_header):
        """Verify the GitHub webhook signature"""
        if not signature_header:
            return False

        # Calculate expected signature
        expected_signature = 'sha256=' + hmac.new(
            WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        # Compare signatures
        return hmac.compare_digest(expected_signature, signature_header)

    def log_message(self, format, *args):
        """Override to customize logging"""
        print(f"{self.address_string()} - {format % args}")


def run_server(port=9000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, WebhookHandler)
    print(f"Webhook server running on port {port}")
    print(f"Listening for GitHub webhooks at http://your-server:{port}/webhook")
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()
