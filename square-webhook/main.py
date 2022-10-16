""" This Cloud Function accepts the webhook invocation from Square, validates that it came from our
    account, and places a message on the orders queue to start processing the order.

    Returns a 200 response code if the message is succesfully published; if there is any error in
    processing the message, a non-200 response code will be returned. This will trigger the retry
    logic of the Square Webhook system.
"""
# pylint: disable=redefined-outer-name,unused-argument,no-member

import base64
import contextvars
import hmac
import json
import os

from hashlib import sha1
from flask import Response
from werkzeug.exceptions import BadRequest, Forbidden, UnsupportedMediaType, MethodNotAllowed, \
    InternalServerError

from google.cloud import pubsub_v1

ctx_id = contextvars.ContextVar("square_order_id", default="")


def log(message, *args, **kwargs):
    """ logs message using structured logging format """
    structured_json = {
        "message": message % args,
    }
    if ctx_id.get() != "":
        structured_json["logging.googleapis.com/labels"] = {
            "square_order_id": ctx_id.get(),
        }

    for key, value in kwargs.items():
        structured_json[key] = value
    print(json.dumps(structured_json))


def validate_message(request):
    """ Validates message is well formed and has valid signature """
    if request.method != 'POST':
        raise MethodNotAllowed(valid_methods="POST")

    content_type = request.headers['content-type']
    if content_type != 'application/json':
        raise UnsupportedMediaType(description=f"Unknown content type: {content_type}")

    # parse the content as JSON
    request_json = request.get_json(silent=False)
    if not request_json or request_json.keys() < {"merchant_id",
                                                  "event_id",
                                                  "data",
                                                  "type"}:
        raise BadRequest(description="JSON is invalid, or missing required property")

    # ensure the request is signed as coming from Square
    try:
        validate_square_signature(request)
    except ValueError as invalid_sig:
        raise Forbidden(description="Signature could not be validated") from invalid_sig

    return request_json


def handle_webhook(request):
    """ Validates that the webhook came from Square and triggers the order creation process.
    This function needs to return with an HTTP 200 within 3 seconds or else the webhook call will
    be retried.
    """
    request_json = validate_message(request)

    ctx_id.set(request_json['data']['id'])

    if 'Square-Initial-Delivery-Timestamp' in request.headers:
        log("Delivery time of initial notification: %s",
            request.headers.get('Square-Initial-Delivery-Timestamp'))

    if 'Square-Retry-Number' in request.headers:
        log("Square has resent this notification %s times; "
            "reason given for the last failure is '%s'",
            request.headers.get('Square-Retry-Number'),
            request.headers.get('Square-Retry-Reason'))

    log(f"{request_json['type']} webhook received", webhook=request_json)

    # put message on topic to upsert order
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(os.environ["GCP_PROJECT"], f"square.{request_json['type']}")
    future = publisher.publish(topic_path, data=json.dumps(request_json).encode('utf-8'))

    # this will block until the publish is complete;
    # or raise an exception if the publish fails which should trigger Square to
    # retry the notification
    try:
        message_id = future.result(timeout=2)
        return Response(message_id, status=200)
    except pubsub_v1.publisher.exceptions.TimeoutError as timeout:
        raise InternalServerError(description="Timeout publishing notification") from timeout
    except Exception as generic_ex:
        raise InternalServerError(description="Unknown error") from generic_ex


def validate_square_signature(request):
    """ Validates the signature for the webhook notification provided within the request.
    The HMAC-SHA1 digest is computed over the concatenation of the URL and the content body.

    The X-Square-Signature HTTP request header specifies the signed digest provided by Square,
    which should match what is calculated in this method.
    """

    key = os.environ['SQUARE_WEBHOOK_SIGNATURE_KEY']
    sig_from_header = request.headers['X-Square-Signature']
    # cloud functions does not set flaskRequest.url with the correct values so we have to munge it
    url = request.url.replace("http", "https").rstrip('/') + '/' + os.environ['FUNCTION_NAME']

    string_to_sign = url.encode('utf-8') + request.data

    # Generate the HMAC-SHA1 signature of the string, signed with your webhook signature key
    string_signature = str(base64.b64encode(hmac.new(key.encode(), string_to_sign, sha1).digest()),
                           'utf-8').rstrip('\n')

    # Compare your generated signature with the signature included in the request
    if not hmac.compare_digest(string_signature, sig_from_header):
        raise ValueError("Square Signature could not be verified")
