from bottle import post, request, run
from random import randrange

import json


@post('/content')
def content():
    team_id = request.json['team_id']
    try:
        with open(f'/srv/example/team_{team_id}') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {
            'answer': randrange(10),
            'denominator': randrange(10)
        }
        data['numerator'] = data['answer'] * data['denominator']
        with open(f'/srv/example/team_{team_id}', 'x') as f:
            json.dump(data, f)
    return {"content": f'Divide {data["numerator"]} by {data["denominator"]}'}


# @post('/callback')
# def callback():
#     pass


@post('/answer')
def answer():
    team_id = request.json['team_id']
    with open(f'/srv/example/team_{team_id}') as f:
        data = json.load(f)
    return {"correct": request.json['guess'] == data['answer']}


if __name__ == '__main__':
    run(host='0.0.0.0')
