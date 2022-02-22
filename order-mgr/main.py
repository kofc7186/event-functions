""" This Cloud Function is triggered on a messaging being published to the 'square.order.created'
    topic.

    It reads the webhook and fetches order, payment, and customer information from Square and
    writes it to a firestore document. Assuming the write to firestore succeeds, we ACK the
    message on the topic.
"""
# pylint: disable=redefined-outer-name,unused-argument,no-member

import base64
import json
import logging
import os
import re

from google.cloud import firestore

from square.client import Client

client = Client(
    access_token=os.environ['SQUARE_ACCESS_TOKEN'],
    square_version='2022-02-16',
    environment=os.environ['SQUARE_ENVIRONMENT'])

SQUARE_LOCATION = os.environ['SQUARE_LOCATION']

LOGGER = logging.getLogger(__name__)

# only configure stackdriver logging when running on GCP
if os.environ.get('FUNCTION_REGION', None):  # pragma: no cover
    from google.cloud import logging as cloudlogging
    LOG_CLIENT = cloudlogging.Client()
    HANDLER = LOG_CLIENT.get_default_handler()
    LOGGER = logging.getLogger("cloudLogger")
    LOGGER.addHandler(HANDLER)


def handle_create(event, context):
    """ This reads the webhook message off of the pub/sub topic and then queries the Square API to get the detailed order,
    payment, and customer objects to persist in firestore.

    If this method throws an Exception, and automatic-retry is enabled, then this will NACK the message to be retried.
    If this method returns without raising an Exception, then the GCF framework will automatically ACK the message.
    """
    # TODO: add webhook message content in a structured way here
    LOGGER.debug("""Received message '{}' from 'square.order.created' topic""".format(context.event_id))

    if 'data' not in event:
        raise KeyError(event)

    webhook_event = json.loads(base64.b64decode(event['data']).decode('utf-8'))

    # webhook event should have structure like:
    # {
    #   "merchant_id": "5S9MXCS9Y99KK",
    #   "type": "order.created",
    #   "event_id": "116038d3-2948-439f-8679-fc86dbf80f69",
    #   "created_at": "2020-04-16T23:14:26.129Z",
    #   "data": {
    #     "type": "order",
    #     "id": "eA3vssLHKJrv9H0IdJCM3gNqfdcZY",
    #     "object": {
    #       "order_created": {
    #         "created_at": "2020-04-16T23:14:26.129Z",
    #         "location_id": "FPYCBCHYMXFK1",
    #         "order_id": "eA3vssLHKJrv9H0IdJCM3gNqfdcZY",
    #         "state": "OPEN",
    #         "version": 1
    #       }
    #     }
    #   }
    # }

    order_id = webhook_event.data.id
    order = get_square_order(order_id)
    customer_id = get_customer_id(order)
    customer = {}

    # the square API is eventually consistent, so the first time we try to
    # extract the customer ID we may need to try again
    if customer_id is None:
        LOGGER.debug("didn't find customer_id on first attempt, retrying")
        order = get_square_order(order_id)
        customer_id = get_customer_id(order)
        if customer_id is None:
            customer = create_faux_customer(order)

    if not customer:
        customer = get_square_customer(customer_id)

    payment_id = get_payment_id(order)
    payment = get_square_payment(payment_id)

    doc = {
        u'order': order,
        u'customer': customer,
        u'payment': payment
    }

    commit_to_firestore(doc)


def get_square_order(order_id: str):
    """ Gets Square Order object for given id value from Square API

    Raises exception if there was any error (transient or invalid order ID)
    """
    orders_api = client.orders

    body = {
        u'location_id': SQUARE_LOCATION,
        u'order_ids': [order_id]
    }

    result = orders_api.batch_retrieve_orders(body)
    if result.is_success():
        return result.body.orders[0]
    return Exception(result)


def get_customer_id(order) -> str:
    """ Extracts the customer ID value from a given order request

    Returns None if it can not be found in order
    """
    if order.fulfillments[0].type == "DIGITAL" and order.customer_id is not None:
        return order.customer_id

    return None


def get_square_customer(customer_id: str):
    """ Gets Square Customer object for given id value from Square API

    Raises exception if there was any error (transient or invalid customer ID)
    """
    customers_api = client.customers

    result = customers_api.retrieve_customer(customer_id)
    if result.is_success():
        return result.body.customer
    return Exception(result)


def create_faux_customer(order):
    """ Creates faux customer object from information within order
    """

    recipient = order.fulfillments[0].pickup_details.recipient
    name_tokens = recipient.display_name.split(" ")

    phone_number = re.sub(r'\+1|\-|\(|\)', "", recipient.phone_number)

    customer = {
        u'given_name': " ".join(name_tokens[:-1]),
        u'family_name': name_tokens[-1],
        u'phone_number': phone_number
    }

    return customer


def get_payment_id(order) -> str:
    """ Extracts the payment ID value from a given order request

    Returns None if it can not be found in order
    """
    return order.tenders[0].id if len(order.tenders) == 1 else None


def get_square_payment(payment_id: str):
    """ Gets Square Payment object for given id value from Square API

    Raises exception if there was any error (transient or invalid payment ID)
    """
    payments_api = client.payments

    result = payments_api.get_payment(payment_id)
    if result.is_success():
        return result.body.payment
    return Exception(result)


def commit_to_firestore(doc: dict):
    """ Writes the combined order, payment, and customer information to firestore
    """

    db = firestore.Client()
    event_ref = db.collection(u'events').document(os.environ['EVENT_DATE'])
    order_counter_ref = event_ref.get('order_counter')
    if not order_counter_ref.exists:
        order_counter_ref.set(1000)
    order_num_result = order_counter_ref.update({"order_counter": firestore.Increment(1)})
    doc.order_number = order_num_result.transform_results[0].integer_value
    #TODO: set order_number back on square order metadata field?

    order_ref = event_ref.collection(u'orders').document(doc.order.id)
    order_ref.set(doc)


def handle_update(event, context):
    """ Webhook fires with this
    {
  "merchant_id": "5S9MXCS9Y99KK",
  "type": "order.updated",
  "event_id": "4b8e5c91-9f17-4cf1-900a-4a0629f81add",
  "created_at": "2020-04-16T23:14:26.359Z",
  "data": {
    "type": "order",
    "id": "eA3vssLHKJrv9H0IdJCM3gNqfdcZY",
    "object": {
      "order_updated": {
        "created_at": "2020-04-16T23:14:26.129Z",
        "location_id": "FPYCBCHYMXFK1",
        "order_id": "eA3vssLHKJrv9H0IdJCM3gNqfdcZY",
        "state": "OPEN",
        "updated_at": "2020-04-16T23:14:26.359Z",
        "version": 2
      }
    }
  }
}
    """
    # fetch order id, customer id, payment id and subsequent objects
    # can call doc_ref.update({
    # u'order':order,
    # u'payment': payment,
    # u'customer': customer
    # })
    # this will keep the atomically incremented order count fixed
    pass