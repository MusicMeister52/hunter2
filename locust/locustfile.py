import time
import json

from locust import HttpUser, task, between, events
import websocket

users = (f'performance{i}' for i in range(1000))

class Player(HttpUser):
    wait_time = between(5, 30)

    def open_puzzle_page(self):
        response = self.client.get('/hunt/ep/1/pz/1/')
        csrftoken = self.client.cookies['csrftoken']
        #return csrftoken
        host = self.host
        if '://' in host:
            host = host[host.find('://')+3:]
        self.ws = websocket.WebSocket()
        cookies = '; '.join('='.join(x) for x in self.client.cookies.items())
        path = '/ws/hunt/ep/1/pz/1/'
        URL = f'ws://{host}{path}'
        while True:
            try:
                start = time.time()
                self.ws.connect(URL, cookie=cookies)
                events.request_success.fire(
                    request_type='WebSocket connect',
                    name=path,
                    response_time=(time.time() - start) * 1000,
                    response_length=0,
                )
                break
            except websocket.WebSocketConnectionClosedException as e:
                events.request_failure.fire(
                    request_type='WebSocket connect',
                    name=path,
                    response_time=(time.time() - start) * 1000,
                    response_length=0,
                    exception=e,
                )
            time.sleep(5)
        self.ws.send(json.dumps({'type': 'guesses-plz', 'from': 'all'}))
        self.ws.send(json.dumps({'type': 'hints-plz', 'from': 'all'}))
        self.ws.send(json.dumps({'type': 'unlocks-plz'}))
        self.ws.recv()

        return csrftoken

    @task(3)
    def incorrect_guesses(self):
        csrftoken = self.open_puzzle_page()
        for i in range(10):
            self.client.post(
                '/hunt/ep/1/pz/1/an',
                data={'answer': '__INCORRECT__', 'csrfmiddlewaretoken': csrftoken}
            )
            time.sleep(self.wait_time())

        self.ws.close()

    #@task
    #def solve_puzzle(self):
    #    csrftoken = self.open_puzzle_page()
    #    for i in range(9):
    #        self.client.post(
    #            '/hunt/ep/1/pz/1/an',
    #            data={'answer': '__INCORRECT__', 'csrfmiddlewaretoken': csrftoken}
    #        )
    #        time.sleep(self.wait_time())
    #    self.client.post(
    #        '/hunt/ep/1/pz/1/an',
    #        data={'answer': 'correct', 'csrfmiddlewaretoken': csrftoken}
    #    )

    def on_start(self):
        name = next(users)
        URL = '/accounts/login/'
        self.client.get(URL)
        csrftoken = self.client.cookies['csrftoken']
        self.client.post(URL, data={'login': name, 'password': name, 'csrfmiddlewaretoken': csrftoken},)
