import functions_framework
from googleapiclient import discovery
import base64


# Triggered from a message on a Cloud Pub/Sub topic.
@functions_framework.cloud_event
def echoservice(cloud_event):

    # Extract attributes received from the payload needed to send a command to the device.
    device_attributes = cloud_event.data["message"]["attributes"]
    device_id = device_attributes.get('deviceId')
    registry_id = device_attributes['deviceRegistryId']
    project_id = device_attributes['projectId']
    region = device_attributes['deviceRegistryLocation']

    # Build message to send back to device
    device_message = cloud_event.data["message"]["data"]
    device_message = base64.b64decode(device_message).decode('utf-8')

    # Append ack to message
    message_to_send = device_message + ' ack'

    # Get the API client
    api_client = discovery.build(
        'cloudiot', 'v1', discoveryServiceUrl=(
            'https://cloudiot.googleapis.com/$discovery/rest'))

    # Send the command to the device
    print('Sending message: {}'.format(message_to_send))
    send_command(api_client, device_id, registry_id, project_id, region,
                 message_to_send)


def send_command(client, device_id, registry_id, project_id, region, command):
    
    # Send a command to a device.
    parent_name = 'projects/{}/locations/{}'.format(project_id, region)
    registry_name = '{}/registries/{}'.format(parent_name, registry_id)
    binary_data = command.encode('utf-8')
    binary_data = base64.b64encode(command.encode('utf-8'))
    binary_data = binary_data.decode('utf-8')

    request = {
        'name': '{}/devices/{}'.format(registry_name, device_id),
        'binaryData': binary_data
    }

    client.projects().locations().registries().devices().sendCommandToDevice(
        name=request['name'], body=request).execute()
