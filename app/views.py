from app import app
from flask import request, jsonify
import shlex
import requests


@app.route("/")
def index():
    return "Hello, World!"


@app.route("/sms-bridge/<cleansweep_instance>/", methods=['GET'])
def handle_request(cleansweep_instance):
    if 'password' not in request.args or not request.args.get('password') or \
            'phone' not in request.args or not request.args.get('phone') or \
            'message' not in request.args or not request.args.get('message'):
        return jsonify(), 400

    cleansweep_instance = cleansweep_instance.upper()
    password_in_config = app.config['{0}_PASSWORD'.format(cleansweep_instance)]
    cleansweep_app_url = app.config['{0}_URL'.format(cleansweep_instance)]

    password = request.args.get('password')
    if password != password_in_config:
        return jsonify(), 401

    phone = request.args.get('phone')

    sms_text = request.args.get('message')
    sms_text_parts = shlex.split(sms_text)  # Splits by whitespace but text in quotes stays intact.

    task = sms_text_parts[0].lower()

    response = _authorize(task, phone, cleansweep_app_url)
    data = response.json()

    is_authorized = response.status_code == 200
    if is_authorized:
        token = data['token']  # Grab token if authorized
        if task == "send-sms":
            response = _send_sms(token, sms_text_parts, cleansweep_app_url)
        else:
            response = None
    else:
        return jsonify({'feedback': data['error']}), response.status_code

    if response is None:
        return jsonify(), 400

    data = response.json()
    is_successful = response.status_code == 200
    return jsonify({"feedback": data['feedback'] if is_successful else data['error']}), response.status_code


def _authorize(task, phone, cleansweep_app_url):
    """
    Authorize the app by sending client-id and client-secret.
    This also checks if user (phone) has permission for the specified task.

    :param task: The task to perform
    :param phone: User's phone number.
    :param cleansweep_app_url: URL where we send our request for authorization.
    :return: Response from the server in a request object.
    This is what the server is going to return:

    If authorized
    200 OK

    {
        "scope": <scope>,
        "phone": <phone>,
        "token": <token>
    }

    If app does not have permission for the specified scope/task.
    403 Forbidden

    {
        "error": "This app does not have permission for <task>"
    }

    If scope/task is invalid.
    400 Bad Request

    {
        "error": "Invalid scope: <task>"
    }

    If no user can be found from that phone number
    404 Not Found

    {
        "error": "No such user found"
    }

    If user does not have permission for the specified task/scope.
    403 Forbidden

    {
        "error": "The user does not have permission for <task>."
    }
    """
    data = {
        'client-id': app.config['CLIENT_ID'],
        'client-secret': app.config['CLIENT_SECRET'],
        'scope': task,
        'phone': phone
    }
    response = requests.post('{0}/api/authorize'.format(cleansweep_app_url), data)
    return response


def _send_sms(token, sms_text_parts, cleansweep_app_url):
    """
    Sends a request to send group sms to all the volunteers of a place.
    :param token: The token to communicate with server
    :param sms_text_parts: The exact sms user sent, split by whitespace.
                            Contains place and the message to send.
    :param cleansweep_app_url: URL where we send our request to send sms.
    :return: Response from the server in a request object.
    This is what the server is going to return:

    If successfully sent
    200 OK

    {
        "feedback": "Your message has been sent to all the volunteers of <sms_text_parts[1]>",
    }

    If token did not match
    400 Bad Request

    {
        "error": "Invalid token: <token>"
    }

    If token gets expired
    400 Bad Request

    {
        "error": "Token expired: <token>"
    }

    If place in sms_text_parts[1] is not a valid place
    400 Bad Request

    {
        "error": "Invalid place: <sms_text_parts[1]>"
    }

    If user does not have permission on that place
    403 Forbidden

    {
        "error": "User does not have permission on: <sms_text_parts[1]>"
    }

    If sms is not configured for that place
    404 Bad Request

    {
        "error": "SMS is not configured for place: <sms_text_parts[1]>"
    }
    """
    if len(sms_text_parts) != 3:  # If sending sms, there can be only 3 parts. 1st task, 2nd place and 3rd the message.
        return None
    data = {
        'token': token,
        'place': sms_text_parts[1],
        'message': sms_text_parts[2]
    }
    return requests.post('{0}/api/send-sms'.format(cleansweep_app_url), data)
