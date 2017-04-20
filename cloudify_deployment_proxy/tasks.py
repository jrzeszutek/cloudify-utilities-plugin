# Copyright (c) 2017 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import tempfile
import time
import urllib

from cloudify import ctx
from cloudify import manager

from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from cloudify_rest_client.exceptions import CloudifyClientError


def poll_with_timeout(pollster,
                      timeout,
                      interval=5,
                      pollster_args={},
                      expected_result=True):

    ctx.logger.debug(
        'pollster: {0}, '
        'timeout: {1}, '
        'interval: {2}, '
        'expected_result: {3}.'
        .format(pollster.__name__,
                timeout,
                interval,
                expected_result))

    current_time = time.time()

    while time.time() <= current_time + timeout:
        ctx.logger.info('Polling client...')
        if pollster(**pollster_args) != expected_result:
            ctx.logger.debug(
                'Still polling.')
            time.sleep(interval)
        else:
            ctx.logger.info(
                'Polling succeeded.')
            return True

    ctx.logger.error('Polling failed.')
    return False


def all_dep_workflows_in_state_pollster(_client, _dep_id, _state):
    _execs = _client.executions.list(deployment_id=_dep_id)
    return all([str(_e['status']) == _state for _e in _execs])


@operation
def wait_for_deployment_ready(state, timeout, **_):

    client = _.get('client') or manager.get_rest_client()
    config = _.get('resource_config') or \
        ctx.node.properties.get('resource_config')
    dep_id = _.get('id') or config.get('deployment_id')

    ctx.logger.info(
        'Waiting for all workflows in '
        'deployment {0} '
        'to be in state {1}.'
        .format(dep_id,
                state))

    pollster_args = {
        '_client': client,
        '_dep_id': dep_id,
        '_state': state
    }
    success = \
        poll_with_timeout(
            all_dep_workflows_in_state_pollster,
            timeout=timeout,
            pollster_args=pollster_args)
    if not success:
        raise NonRecoverableError(
            'Deployment not ready. Timeout: {0} seconds.'.format(timeout))
    return True


@operation
def query_deployment_data(daemonize,
                          interval,
                          timeout,
                          **_):

    if daemonize:
        raise NonRecoverableError(
            'Option "daemonize" is not implemented.')

    client = _.get('client') or manager.get_rest_client()
    config = _.get('resource_config') or \
        ctx.node.properties.get('resource_config')
    dep_id = _.get('id') or config.get('deployment_id')
    outputs = config.get('outputs')

    ctx.logger.debug(
        'Deployment {0} output mapping: {1}'.format(dep_id, outputs))

    try:
        dep_outputs_response = client.deployments.outputs.get(dep_id)
    except CloudifyClientError as ex:
        ctx.logger.error(
            'Ignoring: Failed to query deployment outputs: {0}'
            .format(str(ex)))
    else:
        dep_outputs = dep_outputs_response.get('outputs')

        ctx.logger.debug(
            'Received these deployment outputs: {0}'.format(dep_outputs))
        for key, val in outputs.items():
            ctx.instance.runtime_properties[val] = dep_outputs.get(key, '')
    return True


@operation
def upload_blueprint(tenant='default_tenant', **_):
    client = _.get('client') or manager.get_rest_client()
    config = _.get('resource_config') or \
        ctx.node.properties.get('resource_config')
    app_name = _.get('application_file_name') or config.get('application_file_name')
    bp_archive = _.get('blueprint_archive') or config.get('blueprint_archive')
    bp_id = _.get('blueprint_id') or config.get('blueprint_id') or ctx.instance.id

    try:
        bp_upload_resource = client.blueprints._upload(blueprint_id=bp_id, archive_location=bp_archive, application_file_name=bp_name)
    except CloudifyClientError as ex:
        raise NonRecoverableError('Blueprint failed {0}.'.format(str(ex)))

    ctx.logger.info('Output {0}'.format(bp_upload_resource))