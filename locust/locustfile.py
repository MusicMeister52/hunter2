import time
import json
import urllib.parse

from locust import HttpUser, task, between, constant, events
import websocket

from auth import login

users = ((f'performance{i}', f'performance{i}') for i in range(1000))
admins = ((f'performance-admin{i}', f'performance-admin{i}') for i in range(100))
#users = (('Fish-Test', 'Zzi82v0DJZaYubU') for _ in range(1000))

class Player(HttpUser):
    wait_time = between(5, 30)
    weight = 100

    def open_puzzle_page(self):
        response = self.client.get('/hunt/ep/1/pz/1/')
        host = self.host
        if '://' in host:
            scheme, host = host.split('://')
        csrftoken = self.client.cookies.get('csrftoken', domain=host.split(':')[0])
        cookies = '; '.join('='.join(x) for x in self.client.cookies.items())
        path = '/ws/hunt/ep/1/pz/1/'
        wsscheme = 'ws' if scheme == 'http' else 'wss'
        URL = f'{wsscheme}://{host}{path}'
        while True:
            try:
                self.ws = websocket.WebSocket()
                start = time.time()
                self.ws.connect(URL, cookie=cookies)
                events.request_success.fire(
                    request_type='WebSocket connect',
                    name=path,
                    response_time=(time.time() - start) * 1000,
                    response_length=0,
                )
                break
            except (websocket.WebSocketConnectionClosedException, websocket.WebSocketBadStatusException) as e:
                events.request_failure.fire(
                    request_type='WebSocket connect',
                    name=path,
                    response_time=(time.time() - start) * 1000,
                    response_length=0,
                    exception=e,
                )
            time.sleep(5)
        self.ws.settimeout(5)
        self.ws.send(json.dumps({'type': 'guesses-plz', 'from': 'all'}))
        self.ws.send(json.dumps({'type': 'hints-plz', 'from': 'all'}))
        self.ws.send(json.dumps({'type': 'unlocks-plz'}))
        try:
            while self.ws.recv():
                pass
        except websocket.WebSocketTimeoutException:
            pass

        return csrftoken

    @task(3)
    def incorrect_guesses(self):
        csrftoken = self.open_puzzle_page()
        for i in range(30):
            self.client.post(
                '/hunt/ep/1/pz/1/an',
                data={'answer': '__INCORRECT__', 'csrfmiddlewaretoken': csrftoken}
            )
            time.sleep(self.wait_time())

        self.ws.close()

    @task
    def solve_puzzle(self):
        csrftoken = self.open_puzzle_page()
        for i in range(29):
            self.client.post(
                '/hunt/ep/1/pz/1/an',
                data={'answer': '__INCORRECT__', 'csrfmiddlewaretoken': csrftoken}
            )
            time.sleep(self.wait_time())
        self.client.post(
            '/hunt/ep/1/pz/1/an',
            data={'answer': 'correct', 'csrfmiddlewaretoken': csrftoken}
        )

    def on_start(self):
        user, pw = next(users)
        login(user, pw, self.client, self.host)


class Admin(HttpUser):
    wait_time = constant(5)
    weight = 8

    @task
    def watch_admin_guesses(self):
        self.client.get('/admin/guesses/list?highlight_unlocks=1')

    def on_start(self):
        user, pw = next(admins)
        login(user, pw, self.client, self.host)
