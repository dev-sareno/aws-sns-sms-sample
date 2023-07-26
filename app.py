import json
import base64
import os
import boto3
from botocore.config import Config
from urllib.parse import parse_qs


aws_config = Config(
  region_name = 'ap-southeast-2',
  signature_version = 'v4',
  retries = {
    'max_attempts': 10,
    'mode': 'standard'
  }
)
client = boto3.client('sns', config=aws_config)


def validate_path(request):
  if request['method'] != 'POST' or request['path'] != '/send':  # accepts POST /send only
    return {'statusCode': 404, 'body': 'page not found'}
  return None


def parse_payload(event):
  if 'body' not in event or not event['body']:
    return None, {'statusCode': 400, 'body': 'invalid body'}

  body_b64 = event['body']
  print(f'body_b64={body_b64}')
  
  body = base64.b64decode(body_b64)
  print(f'body={body}')

  # the payload from erpNext is application/x-www-form-urlencoded; parse it
  return parse_qs(body), None


def authenticate(payload):
  error = {'statusCode': 401, 'body': 'unauthorized'}

  if b'authToken' not in payload or not payload[b'authToken']:
    return error
  
  auth_payload = payload[b'authToken']
  print(f'auth_payload={auth_payload}')
  if len(auth_payload) == 0:
    return error
  
  auth_token = os.environ['AUTH_TOKEN']
  print(f'auth_token={auth_token}')
  if auth_payload[0].decode("utf-8") != auth_token:
    return error

  return None


def parse_message(payload):
  if b'message' not in payload or not payload[b'message']:
    return None, {'statusCode': 400, 'body': 'missing: message'}
  return payload[b'message'][0].decode('utf-8'), None


def parse_recipients(payload):
  if b'to' not in payload or not payload[b'to']:
    return None, {'statusCode': 400, 'body': 'missing: to'}
  values = payload[b'to']
  phone_numbers = []
  for value in values:
    phone_numbers.append(value.decode('utf-8'))
  return phone_numbers, None


def lambda_handler(event, context):
  print(event)
  
  try:
    request = event['requestContext']['http']
    headers = event['headers']
    print(f'request={request}')
    print(f'headers={headers}')
    
    # validate path
    error = validate_path(request)
    if error:
      return error

    # parse payload
    payload, error = parse_payload(event)
    if error:
      return error
    print(f'payload={payload}')
    
    # check if authorize
    error = authenticate(payload)
    if error:
      return error
    
    # parse message from payload
    message, error = parse_message(payload)
    if error:
      return error
    print(f'message={message}')
    
    # parse recipients from payload
    recipients, error = parse_recipients(payload)
    if error:
      return error
    print(f'recipients={recipients}')
    
    successful = []  # successful messages
    failed = []  # failed messages
    for recipient in recipients:
      try:
        # send SMS
        print(f'sending sms to {recipient}')
        response = client.publish(
          PhoneNumber=recipient,
          Message=message,
        )
        print(f'response={response}')
        successful.append(recipient)
      except Exception as e:
        print(f'failed to send sms. {e}')
        failed.append(recipient)

    return {
      'statusCode': 200,
      'body': json.dumps({
        'successful': successful,
        'failed': failed,
      })
    }
  except Exception as e:
    return {
      'statusCode': 400,
      'body': json.dumps({
        'message': f'an error has occured. {e}'
      })
    }
