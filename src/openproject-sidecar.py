import requests
import os
import pprint
import json
import yaml
import time
import psycopg2
import sys
import re
import time

print('Starting OpenProject Sidecar ...', flush=True)

ca = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'
token = open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'r').read()
namespace = open('/var/run/secrets/kubernetes.io/serviceaccount/namespace', 'r').read()
deployment = os.environ['OPENPROJECT_DEPLOYMENT']

headers = { 'Authorization': 'Bearer ' + token }
headers_patch = { 
    'Authorization': 'Bearer ' + token,
    'Content-Type': 'application/strategic-merge-patch+json'
}

kubernetes_service_host = os.environ['KUBERNETES_SERVICE_HOST']
kubernetes_port_443_tcp_port = os.environ['KUBERNETES_PORT_443_TCP_PORT']
kubernetes_api_url = 'https://' +  kubernetes_service_host + ':' + kubernetes_port_443_tcp_port

api_namespace = '/api/v1/namespaces/' + namespace
api_namespace_apps = '/apis/apps/v1/namespaces/' + namespace
api_configmaps = '/configmaps'
api_pods = '/pods'
api_deployments = '/deployments'


config_path = '/var/openproject/config'
settings = yaml.load(open(config_path + '/settings', 'r').read(), Loader=yaml.FullLoader)
auth_sources = yaml.load(open(config_path + '/auth_sources', 'r').read(), Loader=yaml.FullLoader)

# Find OpenProject Pod
print('Find OpenProject Pod ...', flush=True)
response = requests.get(kubernetes_api_url + api_namespace + api_pods, headers=headers, verify=ca).content
openproject_pod = ''


for pod in json.loads(response)['items']:
    pod_name = pod['metadata']['name']
    if re.match(rf"{deployment}-\S{{9,10}}-\S{{5,5}}", pod_name):
        openproject_pod = pod_name

if openproject_pod == '':
    print('ERROR: OpenProject Pod not found', flush=True)
    sys.exit(1)
else:
    print('OpenProject Pod found: ' + openproject_pod, flush=True)

# Check for readyness
openproject_ready = False
while not openproject_ready:
    response = requests.get(kubernetes_api_url + api_namespace + api_pods + '/' + openproject_pod, headers=headers, verify=ca).content
    
    for condition in json.loads(response)['status']['containerStatuses']:
        if(condition['name'] == 'openproject' and condition['ready'] != True):
            print('Waiting for OpenProject to be ready ...', flush=True)
            time.sleep(10)
            break
        elif(condition['name'] == 'openproject' and condition['ready'] == True):
            print('OpenProject is ready!', flush=True)
            openproject_ready = True
            break

changed = False

try:
    print('Opening PostgreSQL connection ...')
    connection = psycopg2.connect(user = os.environ['DATABASE_USER'],
                                  password = os.environ['DATABASE_PASSWORD'],
                                  host = os.environ['DATABASE_HOST'],
                                  port = os.environ['DATABASE_PORT'],
                                  database = os.environ['DATABASE_DB'])

    cursor = connection.cursor()

    # Deactivate admin user
    if 'OPENPROJECT_DEACTIVATE_ADMIN' in os.environ:
        if(os.environ['OPENPROJECT_DEACTIVATE_ADMIN'].lower() == "true"):
            print('Deactivating admin users ...', flush=True)
            cursor.execute("UPDATE users SET status=0 WHERE login = 'admin' AND status = 1")
    
    if cursor.rowcount == 1:
        changed = True
    else:
        print("Admin user already deactivated ...", flush=True)

    # Write settings
    for key in settings:
        print('Writing ' + key + '=' + str(settings[key]), flush=True)
        cursor.execute(
            "UPDATE settings SET value=%s "
            "WHERE name = %s AND value != %s", 
            (settings[key], key, str(settings[key])))
        
        if cursor.rowcount == 1:
            changed = True
        else:
            print("Key " + str(key) + " unchanged", flush=True)

        connection.commit()
    
    # Write auth_sources
    for key in auth_sources:
        auth = auth_sources[key]
        print('Writing auth source ' + auth['name'] + ' ...')
        cursor.execute("SELECT name FROM auth_sources WHERE name = %s", [str(auth['name'])])
        
        if cursor.rowcount == 0:
            cursor.execute(
                "INSERT INTO auth_sources (type, name, host, port, account, account_password, base_dn, attr_login, attr_firstname, attr_lastname, attr_mail, onthefly_register, attr_admin, created_at, updated_at, tls_mode, filter_string) "
                f"VALUES ('{auth['type']}', '{auth['name']}', '{auth['host']}', {str(auth['port'])}, '{auth['account']}', '{auth['account_password']}', '{auth['base_dn']}', '{auth['attr_login']}', '{auth['attr_firstname']}', '{auth['attr_lastname']}', '{auth['attr_mail']}', {str(auth['onthefly_register'])}, '{auth['attr_admin'] if auth.get('attr_admin') else ''}', current_timestamp, current_timestamp, {str(auth['tls_mode'])}, '{auth['filter_string'] if auth.get('filter_string') else ''}');")
            
            connection.commit()
            changed = True
        else:
            print("Auth source " + auth['name'] + " unchanged", flush=True)

except (Exception, psycopg2.Error) as error :
    print ('Error while connecting to PostgreSQL: ', error, flush=True)
finally:
    if(connection):
        print('Closing PostgreSQL connection ...', flush=True)
        cursor.close()
        connection.close()

# Restart OpenProject
if changed:
    print('Restarting OpenProject ...', flush=True)

    response = requests.get(kubernetes_api_url + api_namespace_apps + api_deployments + '/' + deployment, headers=headers_patch, verify=ca).content

    original_replica_count = json.loads(response)['spec']['replicas']

    # Scale down
    # This container now get's terminated, before that it needs to re upscale the deployment again!
    data = '{\"spec\":{\"replicas\":0}}'
    response = requests.patch(kubernetes_api_url + api_namespace_apps + api_deployments + '/' + deployment, data, headers=headers_patch, verify=ca).content

    # Scale up again
    data = '{\"spec\":{\"replicas\":' + str(original_replica_count) + '}}'
    response = requests.patch(kubernetes_api_url + api_namespace_apps + api_deployments + '/' + deployment, data, headers=headers_patch, verify=ca).content
else:
    print('No entries changed', flush=True)
    while True:
        time.sleep(1)
