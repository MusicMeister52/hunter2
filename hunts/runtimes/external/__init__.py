# vim: set fileencoding=utf-8 :
from .. import AbstractRuntime

import json
import requests


class ExternalRuntime(AbstractRuntime):
    def evaluate(self, endpoint, team_puzzle_data, user_puzzle_data, team_data, user_data):
        team_id = team_data.team.pk
        user_id = user_data.user.pk
        payload = {
            'team_id': team_id,
            'user_id': user_id,
            'team_puzzle_data': team_puzzle_data.data,
            'user_puzzle_data': user_puzzle_data.data,
            'team_data': team_data.data,
            'user_data': user_data.data,
        }

        r = requests.post(endpoint, json=payload)
        r.raise_for_status()

        response = r.json()
        if 'team_puzzle_data' in response:
            team_puzzle_data = response['team_puzzle_data']
        if 'user_puzzle_data' in response:
            user_puzzle_data = response['user_puzzle_data']
        if 'team_data' in response:
            team_data = response['team_data']
        if 'user_data' in response:
            user_data = response['user_data']

        return response['content']

    def validate_guess(self, endpoint, guess, team_puzzle_data, team_data):
        return False
