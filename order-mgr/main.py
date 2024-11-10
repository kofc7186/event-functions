""" This Cloud Function is triggered on a message being published to the 'square.order.created'
    topic.

    It reads the webhook and fetches order, payment, and customer information from Square and
    writes it to a firestore document. Assuming the write to firestore succeeds, we ACK the
    message on the topic.
"""
# pylint: disable=redefined-outer-name,unused-argument,no-member

import base64
import contextvars
import json
import os
import re

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter, Or

from square.client import Client

firestore_client = firestore.Client()

square_client = Client(
    access_token=os.environ['SQUARE_ACCESS_TOKEN'],
    square_version='2022-09-21',
    environment=os.environ['SQUARE_ENVIRONMENT'])

SQUARE_LOCATION = os.environ['SQUARE_LOCATION']

ctx_id = contextvars.ContextVar("square_order_id", default="")


def log(message, *args, **kwargs):
    """ logs message using structured logging format """
    structured_json = {
        "message": message % args,
    }
    if ctx_id.get() != "":
        structured_json["logging.googleapis.com/labels"] = {
            "square_order_id": ctx_id.get()
        }

    for key, value in kwargs.items():
        structured_json[key] = value
    print(json.dumps(structured_json))


def handle_order_created(event, context):
    """ This reads the webhook message off of the pub/sub topic and then queries the Square API
    to get the detailed order, payment, and customer objects to persist in firestore.

    If this method throws an Exception, and automatic-retry is enabled, then this will NACK the
    message to be retried. If this method returns without raising an Exception, then the GCF
    framework will automatically ACK the message.
    """
    log("Received pubsub message_id '%s' from 'square.order.created' topic", context.event_id)
    webhook_event = json.loads(base64.b64decode(event['data']).decode('utf-8'))

    order = webhook_event['data']['object']['order_created']
    order_id = order['order_id']
    doc = build_doc_from_event(webhook_event)

    commit_to_firestore(doc, order_id=order_id)


def handle_order_updated(event, context):
    """ Webhook fires denoting that there is an update to the Square order object """
    log("Received pubsub message_id '%s' from 'square.order.updated' topic", context.event_id)
    webhook_event = json.loads(base64.b64decode(event['data']).decode('utf-8'))
    doc = build_doc_from_event(webhook_event)

    update_in_firestore(doc)


def handle_payment_updated(event, context):
    """ Webhook fires denoting that there is an update to a Square payment object """
    log("Received pubsub message_id '%s' from 'square.payment.updated' topic", context.event_id)
    webhook_event = json.loads(base64.b64decode(event['data']).decode('utf-8'))

    payment = webhook_event['data']['object']['payment']
    order_id = payment['order_id']

    doc = build_doc_from_event(None, order_id=order_id, payment=payment)
    update_in_firestore(doc)


def handle_customer_updated(event, context):
    """ Webhook fires denoting that there is an update to a Square customer object """
    log("Received pubsub message_id '%s' from 'square.customer.updated' topic", context.event_id)
    webhook_event = json.loads(base64.b64decode(event['data']).decode('utf-8'))

    customer_id = webhook_event['data']['id']

    # search firestore to see if we have any orders referencing this customer ID
    # there may be two cases; one where we knew the customer_id when it was inserted
    event_ref = firestore_client.collection('events').document(os.environ['EVENT_DATE'])
    customer_id_ref = event_ref.collection('orders').where(filter=Or([FieldFilter("customer.id", "==", customer_id),FieldFilter("order.customer_id", "==", customer_id)]))
    results = customer_id_ref.stream()

    # if yes, rebuild for each of those docs
    count = 0
    for result in results:
        count += 1
        doc = build_doc_from_event(None, order_id=result.order.id, customer_id=customer_id)
        update_in_firestore(doc)

    if count == 0:
        log("received update for customer ID %s but no documents matched", customer_id)


def build_doc_from_event(event, order_id=None, payment=None, customer_id=None):
    """ build_doc_from_event builds the dict that represents the order to be written or updated
        in firestore. """
    if not event and not order_id:
        raise Exception("either a webhook event or an order_id must be specified")

    if event and not order_id:
        order_id = event['data']['id']

    ctx_id.set(order_id)
    log("fetching information from Square")

    order = get_square_order(order_id)
#
#    if order['fulfillments'][0]['type'] == "DIGITAL":
#        raise Exception("order is digital, skipping")
#
    if not customer_id:
        customer_id = get_customer_id(order)
    customer = {}

    # the square API is eventually consistent, so the first time we try to
    # extract the customer ID we may need to try again
    if customer_id is None:
        log("customer_id couldn't be found, trying again...")
        order = get_square_order(order_id)
        customer_id = get_customer_id(order)
        if customer_id is None:
            log("customer_id still couldn't be found, creating fake entry")
            customer = create_faux_customer(order)

    if not customer:
        customer = get_square_customer(customer_id)

    if not payment:
        payment_id = get_payment_id(order)
        payment = get_square_payment(payment_id)

    return {
        'order': order,
        'customer': customer,
        'payment': payment
    }


def get_square_order(order_id: str):
    """ Gets Square Order object for given id value from Square API

    Raises exception if there was any error (transient or invalid order ID)
    """
    log("fetching Square order information from Square API")
    orders_api = square_client.orders

    body = {
        'location_id': SQUARE_LOCATION,
        'order_ids': [order_id]
    }

    result = orders_api.batch_retrieve_orders(body)
    if result.is_success():
        log("Square order API response", response=result.body)
        return result.body['orders'][0]
    raise Exception(result)


def get_customer_id(order: dict) -> str:
    """ Extracts the customer ID value from a given order request

    Returns None if it can not be found in order
    """
    # if this is an in-person order, we won't have a customer_id
    if order.get('fulfillments') is None:
        return order.get('customer_id')

    if order['fulfillments'][0]['type'] == "PICKUP" and order.get('customer_id') is not None:
        return order['customer_id']
    elif order['fulfillments'][0]['type'] == "DIGITAL" and order.get('customer_id') is not None:
        return order['customer_id']

    return None


def get_square_customer(customer_id: str):
    """ Gets Square Customer object for given id value from Square API

    Raises exception if there was any error (transient or invalid customer ID)
    """
    customers_api = square_client.customers

    result = customers_api.retrieve_customer(customer_id)
    if result.is_success():
        log("Square customer API response", response=result.body)
        return result.body['customer']
    raise Exception(result)


def create_faux_customer(order):
    """ Creates faux customer object from information within order
    """

    customer = {
        'given_name': "unknown",
        'family_name': "unknown",
        'phone_number': "",
        'version': -1,
    }

    # this will be true for in-person orders with no customer information
    if order.get('fulfillments') is None:
        return customer

    fulfillments = order['fulfillments'][0]
    if fulfillments['type'] == "DIGITAL":
        return customer

    pickup_details = fulfillments['pickup_details']
    recipient = pickup_details['recipient']

    name_tokens = recipient['display_name'].split(" ")

    phone_number = "unknown"
    if recipient.get('phone_number'):
        phone_number = re.sub(r'\+1|\-|\(|\)|\s', "", recipient['phone_number'])

    customer = {
        'given_name': " ".join(name_tokens[:-1]),
        'family_name': name_tokens[-1],
        'phone_number': phone_number,
        'version': -1,
    }

    return customer


def get_payment_id(order) -> str:
    """ Extracts the payment ID value from a given order request

    Returns None if it can not be found in order
    """
    return order['tenders'][0]['id'] if len(order.get('tenders',[])) == 1 else None


def get_square_payment(payment_id: str):
    """ Gets Square Payment object for given id value from Square API

    Raises exception if there was any error (transient or invalid payment ID)
    """
    payments_api = square_client.payments

    if not payment_id:
        raise Exception("asked for a None payment")

    result = payments_api.get_payment(payment_id)
    if result.is_success():
        log("Square payment API response", response=result.body)
        return result.body['payment']
    raise Exception(result)


def commit_to_firestore(doc: dict):
    """ Writes the combined order, payment, and customer information to firestore """

    event_ref = firestore_client.collection('events').document(os.environ['EVENT_DATE'])
    order_ref = event_ref.collection('orders').document(doc['order']['id'])
    if order_ref.get().exists:
        raise Exception("document already exists in firestore")

    order_counter_ref = event_ref.get(['order_counter'])
    if not order_counter_ref.exists:
        event_ref.set({"order_counter": 1000})
    order_num_result = event_ref.update({"order_counter": firestore.Increment(1)})
    doc['order_number'] = order_num_result.transform_results[0].integer_value
    # TODO: set order_number back on square order metadata field?

    set_result = order_ref.set(doc)
    log("document committed to firestore: %s", set_result)


def update_in_firestore(doc: dict):
    """ Updates the combined order, payment, and customer information to firestore """

    event_ref = firestore_client.collection('events').document(os.environ['EVENT_DATE'])
    order_ref = event_ref.collection('orders').document(doc['order']['id'])
    order_doc = order_ref.get()
    if order_doc.exists:
        update_doc = {}

        curr_order = order_doc.to_dict()
        if curr_order['order']['version'] > doc['order']['version']:
            update_doc['order'] = doc['order']
        if curr_order['payment']['updated_at'] > doc['payment']['updated_at']:
            update_doc['payment'] = doc['payment']
        curr_customer_version = curr_order['customer'].get('version')
        if not curr_customer_version or curr_customer_version > doc['customer']['version']:
            update_doc['customer'] = doc['customer']
        if len(update_doc.items()) > 0:
            update_result = order_ref.update(update_doc)
            log("updated firestore based on square update %s", update_result)
        else:
            log("skipped update since newer information is already persisted for record",
                curr_order=curr_order)
    else:
        log("update failed because entry doesn't exist in firestore; adding entry")
        commit_to_firestore(doc)
