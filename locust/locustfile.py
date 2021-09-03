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
        # This method is not a locust task; it is called be the other puzzle interaction
        # tasks.
        # Get the puzzle page. Simulates the user and gets us the CSRF Token.
        response = self.client.get('/hunt/ep/1/pz/1/')

        # Boring stuff to allow us to connect
        host = self.host
        if '://' in host:
            scheme, host = host.split('://')
        csrftoken = self.client.cookies.get('csrftoken', domain=host.split(':')[0])
        cookies = '; '.join('='.join(x) for x in self.client.cookies.items())
        path = '/ws/hunt/ep/1/pz/1/'
        wsscheme = 'ws' if scheme == 'http' else 'wss'
        URL = f'{wsscheme}://{host}{path}'

        # end boring stuff

        # Try to connect to the websocket forever
        while True:
            try:
                self.ws = websocket.WebSocket()
                start = time.time()
                self.ws.connect(URL, cookie=cookies)
                # register the event for locust
                events.request_success.fire(
                    request_type='WebSocket connect',
                    name=path,
                    response_time=(time.time() - start) * 1000,
                    response_length=0,
                )
                break
            except (websocket.WebSocketConnectionClosedException, websocket.WebSocketBadStatusException) as e:
                # The first of these exceptions is weird.
                # register the failure for locust
                events.request_failure.fire(
                    request_type='WebSocket connect',
                    name=path,
                    response_time=(time.time() - start) * 1000,
                    response_length=0,
                    exception=e,
                )
            time.sleep(5)

        # once here we've successfully connected: send what the client would send.
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
        """Load the puzzle page, connect to the websocket, and guess incorrectly 30 times"""
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
        """Load the puzzle page, connect to the websocket and incorrectly 29 times then guess "correct" once

        (make that the answer to the puzzle to make this work)
        """
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
