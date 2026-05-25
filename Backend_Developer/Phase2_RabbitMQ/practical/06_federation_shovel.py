"""
RabbitMQ Federation + Shovel — Production Patterns
"""

import requests
from requests.auth import HTTPBasicAuth


# ==========================================================================
# 1. ENABLE PLUGINS
# ==========================================================================

PLUGIN_SETUP = """
# Federation
rabbitmq-plugins enable rabbitmq_federation
rabbitmq-plugins enable rabbitmq_federation_management

# Shovel
rabbitmq-plugins enable rabbitmq_shovel
rabbitmq-plugins enable rabbitmq_shovel_management


# Verify
rabbitmq-plugins list | grep -E 'federation|shovel'
"""


# ==========================================================================
# 2. FEDERATION via CLI
# ==========================================================================

FEDERATION_CLI_SETUP = """
# On DOWNSTREAM broker, define upstream
rabbitmqctl set_parameter federation-upstream my-upstream \\
    '{"uri": "amqp://repl-user:strong-pass@upstream-host:5672/%2f", \\
      "expires": 3600000, \\
      "prefetch-count": 1000}'

# Policy: federate all 'events.*' exchanges
rabbitmqctl set_policy \\
    --apply-to exchanges \\
    federate-events "^events\\." \\
    '{"federation-upstream-set": "all"}'

# Or specific upstream
rabbitmqctl set_policy --apply-to exchanges federate-events "^events\\." \\
    '{"federation-upstream": "my-upstream"}'


# Federated queue (consumers downstream consume upstream queue)
rabbitmqctl set_policy \\
    --apply-to queues \\
    federate-queue "^federated\\." \\
    '{"federation-upstream-set": "all"}'


# Verify
rabbitmqctl federation_status
"""


# ==========================================================================
# 3. FEDERATION via HTTP API
# ==========================================================================

MGMT_URL = "http://downstream-host:15672"
AUTH = HTTPBasicAuth('admin', 'admin')


def add_federation_upstream(name: str, uri: str, vhost: str = '%2F'):
    requests.put(
        f'{MGMT_URL}/api/parameters/federation-upstream/{vhost}/{name}',
        auth=AUTH,
        json={
            'value': {
                'uri': uri,
                'expires': 3600000,
                'prefetch-count': 1000,
                'reconnect-delay': 5,
            },
        },
    )


def add_federation_policy(
    name: str,
    pattern: str,
    upstream: str = 'all',
    vhost: str = '%2F',
):
    requests.put(
        f'{MGMT_URL}/api/policies/{vhost}/{name}',
        auth=AUTH,
        json={
            'pattern': pattern,
            'apply-to': 'exchanges',
            'definition': {
                'federation-upstream-set': upstream,
            },
            'priority': 0,
        },
    )


# Usage
# add_federation_upstream('us-east-upstream', 'amqp://repl:pass@us-east-broker:5672/')
# add_federation_policy('federate-events', '^events\\.', upstream='all')


# ==========================================================================
# 4. SHOVEL via CLI
# ==========================================================================

SHOVEL_CLI_SETUP = """
# Dynamic shovel
rabbitmqctl set_parameter shovel my-shovel \\
    '{
        "src-protocol": "amqp091",
        "src-uri": "amqp://src-user:pass@source-broker:5672/%2f",
        "src-queue": "source-queue",
        "src-prefetch-count": 100,
        "dest-protocol": "amqp091",
        "dest-uri": "amqp://dest-user:pass@dest-broker:5672/%2f",
        "dest-exchange": "dest-exchange",
        "dest-exchange-key": "routing-key",
        "ack-mode": "on-confirm",
        "delete-after": "never"
    }'


# Or via static config (rabbitmq.conf)
# shovel.my-shovel.source.uri = amqp://...
# shovel.my-shovel.source.queue = source-q
# shovel.my-shovel.destination.uri = amqp://...
# shovel.my-shovel.destination.exchange = dest-ex


# Verify
rabbitmqctl shovel_status


# Remove
rabbitmqctl clear_parameter shovel my-shovel
"""


# ==========================================================================
# 5. SHOVEL via HTTP API
# ==========================================================================

def add_shovel(
    name: str,
    src_uri: str,
    src_queue: str,
    dest_uri: str,
    dest_exchange: str,
    dest_routing_key: str = '',
    vhost: str = '%2F',
):
    requests.put(
        f'{MGMT_URL}/api/parameters/shovel/{vhost}/{name}',
        auth=AUTH,
        json={
            'value': {
                'src-protocol': 'amqp091',
                'src-uri': src_uri,
                'src-queue': src_queue,
                'src-prefetch-count': 100,
                'dest-protocol': 'amqp091',
                'dest-uri': dest_uri,
                'dest-exchange': dest_exchange,
                'dest-exchange-key': dest_routing_key,
                'ack-mode': 'on-confirm',     # most reliable
                'delete-after': 'never',
            },
        },
    )


def remove_shovel(name: str, vhost: str = '%2F'):
    requests.delete(
        f'{MGMT_URL}/api/parameters/shovel/{vhost}/{name}',
        auth=AUTH,
    )


def list_shovel_status():
    resp = requests.get(f'{MGMT_URL}/api/shovels', auth=AUTH)
    for shovel in resp.json():
        print(f"{shovel['name']:30} {shovel['state']:10} {shovel.get('last_changed', '')}")


# ==========================================================================
# 6. MIGRATION PATTERN (Shovel)
# ==========================================================================

MIGRATION_PATTERN = """
# Scenario: Migrate from old broker to new broker

# Step 1: Set up shovel to move all queues' messages
for queue in ['orders', 'payments', 'notifications']:
    add_shovel(
        name=f'migrate-{queue}',
        src_uri='amqp://user:pass@OLD-broker:5672/',
        src_queue=queue,
        dest_uri='amqp://user:pass@NEW-broker:5672/',
        dest_exchange='',     # default exchange = direct to queue
        dest_routing_key=queue,
    )

# Step 2: Switch publishers to NEW broker
# (App config update + deploy)

# Step 3: After old broker drained (queue length = 0), switch consumers
# (Stop reading from OLD, start from NEW)

# Step 4: Remove shovels
for queue in ['orders', 'payments', 'notifications']:
    remove_shovel(f'migrate-{queue}')
"""


# ==========================================================================
# 7. EDGE → CLOUD AGGREGATION (Federation)
# ==========================================================================

EDGE_TO_CLOUD = """
# Each edge broker (us-east, eu-west, ap-south) federates 'iot.*' exchanges
# to central broker for processing

# On central broker, define each edge as upstream
add_federation_upstream('edge-us-east', 'amqp://central-puller:pass@us-east:5672/')
add_federation_upstream('edge-eu-west', 'amqp://central-puller:pass@eu-west:5672/')
add_federation_upstream('edge-ap-south', 'amqp://central-puller:pass@ap-south:5672/')


# Policy on central: federate iot.* from all edges
add_federation_policy('federate-iot', '^iot\\.', upstream='all')


# Now central sees union of all edges' iot.* events
# Consumers on central can subscribe with full visibility
"""


# ==========================================================================
# 8. CROSS-DC DISASTER RECOVERY
# ==========================================================================

DR_PATTERN = """
# Primary DC processes traffic
# DR DC has continuous shovel of important queues

for critical_queue in ['orders', 'payments']:
    add_shovel(
        name=f'dr-{critical_queue}',
        src_uri='amqp://shovel:pass@primary-dc:5672/',
        src_queue=critical_queue,
        dest_uri='amqp://shovel:pass@dr-dc:5672/',
        dest_exchange='',
        dest_routing_key=critical_queue,
    )

# On disaster: app traffic flips to DR DC
# DR DC has recent messages already
# Resume consumers there


# Monitor DR queue length vs primary queue length to ensure shovel keeping up
"""


# ==========================================================================
# 9. FEDERATION LOOP PROTECTION
# ==========================================================================

LOOP_PROTECTION = """
# Bidirectional federation (A → B and B → A) can cause loops

# Protection 1: max-hops in federation policy
add_federation_policy('federate-events-safe', '^events\\.', upstream='all')
# This sets max-hops=1 by default — message stops after one federation hop

# Protection 2: distinct exchange prefixes per region
# Region A publishes to 'us-east.events.X'
# Region B publishes to 'eu-west.events.X'
# Federation routes only specific prefixes → no loop possible


# Protection 3: Message headers
# Add x-region header on publish
# Federation policy filters out messages from same region (using exchange-side routing)
"""


# ==========================================================================
# 10. MONITORING
# ==========================================================================

def federation_health():
    """Get federation link status."""
    resp = requests.get(f'{MGMT_URL}/api/federation-links', auth=AUTH)
    for link in resp.json():
        print(f"{link['upstream']:20} {link['type']:10} {link['status']}")
        if link['status'] != 'running':
            print(f"  ALERT: link {link['upstream']} not running")


def shovel_health():
    """Get shovel link status."""
    resp = requests.get(f'{MGMT_URL}/api/shovels', auth=AUTH)
    for shovel in resp.json():
        state = shovel['state']
        print(f"{shovel['name']:30} {state}")
        if state == 'terminated' or 'error' in state:
            print(f"  ALERT: shovel {shovel['name']} broken: {shovel.get('reason', '')}")


# ==========================================================================
# 11. PROMETHEUS METRICS
# ==========================================================================

PROMETHEUS_METRICS = """
# rabbitmq_prometheus plugin exposes:

rabbitmq_federation_link_state          # 0=down, 1=running
rabbitmq_shovel_state                   # state per shovel

rabbitmq_queue_messages                 # backlog per queue
rabbitmq_queue_messages_ready
rabbitmq_queue_consumers


# Alerts
- federation_link_state == 0 for > 5m
- shovel_state != 'running' for > 1m
- queue_messages > N (backlog)
- federation_lag (custom — compare upstream queue length)
"""
