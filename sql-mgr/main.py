""" This Cloud Function is triggered on a new order document being written to Firestore.

    It reads the document and:
     - creates a label/printout for the order and stores it in GCS
     - adds a row to CloudSQL table
"""
# pylint: disable=redefined-outer-name,unused-argument,no-member

import contextvars
from datetime import datetime
import json
import os
import re
import urllib.parse

from flask import Response, Request
from google.cloud import storage, firestore, pubsub_v1
from werkzeug.exceptions import NotFound

GCS_BUCKET = os.environ['GCS_BUCKET']


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


# Instantiates a firestore client
fs_client = firestore.Client()
collection_path = f"events/{os.environ['EVENT_DATE']}/orders"

# Instantiates a storage client
client = storage.Client()
bucket = client.get_bucket(GCS_BUCKET)


def fetch_document_from_firestore(doc_id):
    """ this grabs the document from Firestore and returns as a DocumentSnapshot """

    # extract relevant document & collection paths
    doc = fs_client.collection(collection_path).document(doc_id)

    doc_snap = doc.get()

    if doc_snap.exists:
        return doc_snap, doc

    raise KeyError(f"could not find {doc_id} in Firestore")


def get_label_bytes(self_link):
    """ downloads label from GCS using self_link """
    # get path to object within bucket
    label_ref = urllib.parse.unquote(self_link.removeprefix(
        "https://www.googleapis.com/storage/v1/b/kofc7186-fishfry/o/"))
    return bucket.get_blob(label_ref).download_as_bytes()


def send_pdf_to_topic(pdf_bytes, order_id, reprint=False):
    """ sends PDF to print_queue topic """

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(os.environ["GCP_PROJECT"], "print_queue")

    reprint_str = ""
    if reprint:
        reprint_str = "true"

    #   push onto print_queue
    future = publisher.publish(topic_path,
                               data=pdf_bytes,
                               son=order_id,
                               reprint=reprint_str)

    # this will block until the publish is complete
    message_id = future.result(timeout=2)
    log(f"print request on queue with message id {message_id}")


def handle_print(request: Request):
    """ Prints a document """
    reprint = request.args.get("reprint", "").lower()
    request_json = request.get_json()
    order_id = request_json['Data']['id']
    ctx_id.set(order_id)
    log("recieved print webhook", appsheet_json=request_json)

    # payload.id contains the square order ID since this is reading the datastream JSON
    firestore_doc_snap, firestore_doc = fetch_document_from_firestore(order_id)
    firestore_dict = firestore_doc_snap.to_dict()
    print_times = firestore_dict.get('print_times')
    if print_times:
        # if this is there, we've printed this doc before, skip it
        log("doc has already been printed before, skipping", print_times=print_times)
        return Response(status=400)

    log("no prior printing detected, fetching label and sending to print queue")
    if request_json['Data']['label_url']:
        label_bytes = get_label_bytes(request_json['Data']['label_url'])

        send_pdf_to_topic(label_bytes,
                          request_json['Data']['square_order_number'],
                          reprint == "true")
    else:
        log("couldn't find label_url")
        return Response(status=400)

    if reprint != "true":
        # datetime object containing current date and time
        now = datetime.now()

        dt_string = now.strftime("%m/%d/%Y %H:%M:%S")
        firestore_doc.update({
            "pickup": {
                "status": "ARRIVED",
                "checkin_time": request_json['Data']['checkin_time'],
            },
            "print_times": [dt_string]
        })

    return Response(status=200)
