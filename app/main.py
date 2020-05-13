import os
import boto3
import json
import time
import requests
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

TOKEN = open('/var/run/secrets/kubernetes.io/serviceaccount/token', 'r').read()
API_HOST = os.environ['KUBERNETES_SERVICE_HOST']
REGION = os.environ['REGION']

s = requests.Session()
s.headers.update({'Authorization': 'Bearer ' + TOKEN})
ec2 = boto3.client('ec2', region_name=REGION)
asg = boto3.client('autoscaling', region_name=REGION)


def get_url(url):
    return 'https://' + API_HOST + url


def get_nodes():
    nodes = s.get(get_url('/api/v1/nodes'), verify=False)
    return list(map(lambda x: {'name': x['metadata']['name'],
                               'id': x['spec']['externalID'],
                               'labels': x['metadata']['labels']},
                    json.loads(nodes.content)['items']))


def tag_nodes():
    for node in get_nodes():
        nodeLabels = node['labels']
        ec2Labels = {}
        autoscaling_group = ''
        tags_ec2 = ec2.describe_instances(
            InstanceIds=[
                node['id']
            ])['Reservations'][0]['Instances'][0]['Tags']

        for tag in tags_ec2:
            str_clean = lambda x: x.replace(':', '.').replace('/', '-')
            key = str_clean(tag['Key'])
            value = str_clean(tag['Value'])
            ec2Labels.update({key: value})
            if tag['Key'] == 'aws:autoscaling:groupName':
                autoscaling_group = tag['Value']

        if len(autoscaling_group):
            tags_asg = asg.describe_auto_scaling_groups(
                AutoScalingGroupNames=[
                    autoscaling_group
                ])['AutoScalingGroups'][0]['Tags']

            for tag in tags_asg:
                str_clean = lambda x: x.replace(':', '.').replace('/', '-')
                key = str_clean(tag['Key'])
                value = str_clean(tag['Value'])
                ec2Labels.update({key: value})

        # Only patch k8s node labels if they are missing something from EC2 or ASG
        if all(item in nodeLabels.items() for item in ec2Labels.items()) is False:
            print ec2Labels

            body = {
                'kind': 'Node',
                'metadata': {
                    'labels': ec2Labels
                }
            }

            s.patch(get_url('/api/v1/nodes/' + node['name']),
                    json=body,
                    headers={'Content-Type': 'application/merge-patch+json'},
                    verify=False)

            time.sleep(0.5)

while True:
    try:
        time.sleep(30)
        tag_nodes()
    except Exception as e:
        print e
