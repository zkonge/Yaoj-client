from typing import Tuple, Union
import os
import sys
import json
import time
import tempfile
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler

CLIENT_VERSION = (0, 0, 1)


def check() -> None:
    version = sys.version_info
    if version < (3, 7):
        sys.stderr.write('This program need Python 3.7 or newer, your Python version {}.{}.{}'.format(*version))
        time.sleep(3)
        exit(1)


class HTTPRequestHandler(BaseHTTPRequestHandler):
    def get(self) -> Union[dict, Tuple[dict, int]]:
        """Yaoj client info"""
        return {'python_version': sys.version_info[:3],
                'client_version': CLIENT_VERSION,
                'protocol_version': self.protocol_version}

    def post(self) -> Union[dict, Tuple[dict, int]]:
        """Run code for each test case"""
        if self.headers.get('content-type') != 'application/json':
            return {'message': 'request type not allowed'}, 403

        content_length = int(self.headers.get('content-length'))
        request = json.loads(self.rfile.read(content_length).decode())

        """
        request={
            'code': 'user code',
            'test_cases': [
                {'code_prefix': 'A=[1,2,3,4,5]\nB=[5,4,3,2,1]'},
                {'code_prefix': 'A=[2,3,4,5,5]\nB=[6,6,6,6,6]'}
            ]
        }
        """

        results = []

        for i, test_case in enumerate(request['test_cases']):
            # A file can't be opened by more than one process in Windows
            temp_file = tempfile.NamedTemporaryFile('w', delete=False)
            temp_file.write(test_case['code_prefix'] + '\n' + request['code'])
            temp_file.close()

            try:
                result = subprocess.run([sys.executable, temp_file.name], timeout=5, capture_output=True)
                results.append({
                    'return_code': result.returncode,
                    'stdout': result.stdout.decode().replace('\r\n', '\n'),
                    'stderr': result.stderr.decode().replace('\r\n', '\n')
                })
            except subprocess.TimeoutExpired:
                print(f'Time Limit Exceeded in test case {i + 1}')
                results.append({
                    'return_code': -1,  # Program always return a positive code, so -1 means TLE
                    'stdout': '',
                    'stderr': ''
                })

            os.unlink(temp_file.name)  # Clean up the battlefield

        return {'results': results}

    def put(self) -> Union[dict, Tuple[dict, int]]:
        """Self update"""
        if self.headers.get('content-type') != 'application/json':
            return {'message': 'request type not allowed'}, 403

        content_length = int(self.headers.get('content-length'))
        request = json.loads(self.rfile.read(content_length).decode())

        try:
            if request['client_version'] > CLIENT_VERSION:
                with open(__file__, 'w') as f:
                    f.write(request['client_code'])
                return {'message': 'update ok'}
            return {'message': 'up to date'}
        except Exception as e:
            return {'message': e.args[0]}, 500

    def do_GET(self) -> None:
        self.wrap_resp(self.get())

    def do_POST(self) -> None:
        self.wrap_resp(self.post())

    def do_PUT(self) -> None:
        self.wrap_resp(self.put())

    def wrap_resp(self, resp) -> None:
        if isinstance(resp, tuple):
            self.send_response(resp[1])
            resp = resp[0]
        else:
            self.send_response(200)
        self.send_headers()
        self.wfile.write(json.dumps(resp).encode())

    def send_headers(self) -> None:
        origin = self.headers.get('origin', 'https://yaoj.konge.pw/')
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT')
        self.end_headers()


def run(address: Tuple[str, int], http_handler=HTTPRequestHandler) -> None:
    httpd = HTTPServer(address, http_handler)
    httpd.serve_forever()


if __name__ == '__main__':
    check()
    run(('127.0.0.1', 23333))
