# Copyright (C) 2019 The Hunter2 Contributors.
#
# This file is part of Hunter2.
#
# Hunter2 is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any later version.
#
# Hunter2 is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License along with Hunter2.  If not, see <http://www.gnu.org/licenses/>.

import boto3
import json

from .abstract import AbstractFaasRuntime
from ..exceptions import RuntimeExecutionError, RuntimeExecutionTimeExceededError


class AwsLambdaRuntime(AbstractFaasRuntime):
    def __init__(self, boto3_session=None):
        if boto3_session is None:
            boto3_session = boto3.Session()
        self.boto3_session = boto3_session

    def check_metadata(self, function_metadata):
        for k in ['region', 'function_name']:
            if k not in function_metadata:
                return False
        return True

    def call(self, function_metadata, state_dict):
        lambda_client = self.boto3_session.client('lambda', region_name=function_metadata['region'])
        state_json = json.dumps(state_dict)
        invoke_response = lambda_client.invoke(FunctionName=function_metadata['function_name'], Payload=state_json)
        payload = json.load(invoke_response['Payload'])
        if invoke_response.get('FunctionError') is not None:
            raise RuntimeExecutionError(payload.get("errorMessage", 'Failed Lambda Execution'))
        return payload
