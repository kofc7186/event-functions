import base64
import contextvars
import json
import os
import re

from google.cloud import firestore

from square.client import Client

square_client = Client(
    access_token=os.environ['SQUARE_ACCESS_TOKEN'],
    square_version='2022-02-16',
    environment=os.environ['SQUARE_ENVIRONMENT'])

SQUARE_LOCATION = os.environ['SQUARE_LOCATION']

ctx_id = contextvars.ContextVar("square_order_id", default="")


def get_times():
#    orders = ["3nRYmSNprNrhInXTRnTt6wKy9V6YY", "nTZVf7WZE77sJ910yX6iWrVZtXUZY", "xm22QMKNsw4io3phCwxEu2iEswBZY", "fVMjmfX7S9sSBns2D374o6Ye8kRZY", "jtp6DSzxpZnbFkqdkIQbh9frL8cZY", "RSahsSNRw0DZ9lefUNNvkB1G1i9YY", "XzHcSQXBdN7I0KHwKQpCrwcJItUZY", "L3M2VDjPS1nQtSgitXlNwbvFmcLZY", "znQfcfpww9rR7mtWY9gcCpAbPzfZY", "HZI5mMbOGHb22NChbdytRQG9JWAZY", "7nqH7CERtLdITtXInAhZm9r9XmEZY", "xo7gI81O64btezOXTK0gMyFMnhGZY", "h2wfjtoR8k3vutt530jv5VJhQgOZY", "ZIFGgLUxUA8g5VdevTo0KoonwkbZY", "39s67Gn5oAjLNxIzyxKp8uvvYnAZY", "jbSFc08qjurchjC8UmQsTtBzhJQZY", "xa4ewvcXdTaYrrtBRtmkeB9QU2eZY", "j7SZMt6hCVMKm89sO4YKIZOcdSLZY", "TfQ5cakHtnkqfGkobAA2nbFEkqdZY", "D1f9imZGM4pKZgjkoZ3klcp8uoUZY", "tEmmsYjuMZTVy4UtzvAtalNfWzEZY", "XpysC6VZtJboeutDnWYOsLTVAgFZY", "hmaOACwUTJgFD5LcybkcBSSyMQaZY", "TbgSeJjuVSiqWBXLRpBqZrtKBmYZY", "xGE58NgIBhdXcXWvagxU3znBpUUZY", "7nSDFBqdbIcxEvNctKQEg5x4KxPZY", "nTh5pC126eDy39b0nF4OsK0XQUVZY", "HXDD0EdnkDdt8eoLE2m7LMRvJq8YY", "piMD7FCyU0BKpeMTszKJHUihAQNZY", "fl4fJ2nFbzkDORXO5y9viO5U5oTZY", "5qQTGvshsQHWAdF24mIs9xbkoFZZY", "9uDe3Zb5wm8cSRyevtNxcSz2YbPZY", "TLC7mkvtvrOB4xEjEvHunxzUau6YY", "pWWfbkqvk8LKqQcr6rpHs0m8If7YY", "dShovn9IUMu4aLY2kJzgRspyTfeZY", "zpzUQwdjA8c4U0ij8sxkpEVSPaLZY", "z7EWpFPXeKsugjLZ3FYVUHTfMsdZY", "jV5U7tUZpQkvenvrW17CV1pEpUQZY", "lgMbZcv460Ih3KxOCyK1HDCZjGgZY", "RWWmGVXmbqw2Ic1m3YIJuQcZspYZY", "ZeOFWKy0zzF7NmmahycrR9pRBkcZY", "zTssZdAuNQSzNGOoWfZjhpbixjZZY", "PjdqsfWqAwwNYn4JVyryh2NgfJZZY", "TLqfcpW1HAdqWOcTnTMNdDGicX9YY", "TRhlwWrTdkdnE8CFLL57Fr1PQRbZY", "NEwltDCtUM0AJK3KVWAUC8PcedDZY", "10C5WJptWjIgzkA8SLu4cY6eZrNZY", "piEHzdbBNcHcbSGPXp1itYRxH2eZY", "p60Z3zbgr6QHUZtJCQGpkMsfKhIZY", "PZUUu1W3CpNk58rRacjfYzjLG1WZY", "3FQEUeoQbQ3MWGcMQs7NPJIu7YJZY", "Rgp3vReIdesBzxO3CukzXngVuKBZY", "p4HrnzGQeNE9vOPbcRdHEpYVxyMZY", "9Or2LAT6kHt3rmlGOd1589KYbeJZY", "tCZK7RVLrz1IkakCKBpdkIxSG9TZY", "V2Vg3B9yBBA678FsRiHwI6ASeaaZY", "HVUWNUS74gBgKYupIXAokz6qhUFZY", "bL6QMhf74CdULd0vhjdHIB3t8XWZY", "tGR3qMj0cGIHlcVVGDiILMDckTFZY", "V6BZl39cMSpZJIiGDIAKoIsVXAVZY", "bhNQWnvMFzHB3H4kGjWYRJ38WJLZY", "tyDxQyARPUcYE2U37Gj8INhWJGAZY", "LpH5G16BGH7eFo4Js3vrEme9M0TZY", "ps59Wt8dY4PsdSjtUDPMiwyZDQRZY", "N6P3bqyrw58LnoAF5IJ7gxgFm7WZY"]
#    orders = ["LPyv12qy67lrpXCIRSQjexp8wZRZY", "v9sHIVHintzFKgcVIv7RiDqHReSZY", "jZvsuZLcLbN8BpKwOgHUFydHEtXZY", "x89GLhWhq4WFNbgye4d6fQ42m4FZY", "Tv2yxEb4OhWZ0If1xDcYVlYQHbNZY", "Z47vZbNnlj97eJyo5Mi84dY3MIdZY", "3JEhoxDBz0YsJMTTjXMxdRyeBaHZY", "TbIeG1k9qzmiWI6Fjf2Xd5AY37HZY", "RkxUOyaiCbfHX8cSqIjrpnDTCmSZY", "jjg2gz0sEMsN0HURyxDjYLXzOCSZY", "d6Rcmhd44fZiU05XNHfy2y6XwFHZY", "FsyHpEvc8Z9Dksst1EjZXJ5K6PTZY", "BIncYTnrITzemLyPTrE6lO7RcYGZY", "Djm7LtbSJq4EJy7v8LiP4Q5MIB9YY", "3jnM2WERRMNBIChHucirT3dMtEFZY", "D1xYtH1s7smWeEArPKOQyUPDYBaZY", "ZioDRFHQ6VhV9sCbsMOrBznKDTMZY", "1AcNlSP0DgluS2U0XszL268PUhBZY", "RWmiUxoqZrcKw64hP9U76zAT4dAZY", "Z4rXRPHbZ0NLfcOlZzAbSzYaF69YY", "N2DcMcM7GnJI05CVbmDbpnHCbm7YY", "fFieOuCl20xqb1MDswwhDKRX0wYZY", "Tl5eloTaLTGXn15eBuZwuaKkfyVZY", "jVNAot3WWzqpKcaQOyVomt6JqbSZY", "1gmODETfL4s1rLAcEd7el9a0Vl6YY", "lG5ApWnMXSxLnW4yevtwRUYDXAXZY", "dWfaZnDrGF8QnVom011MRCKkppdZY", "VkOtZb1unuY1nLzLrDBa5TPUIPKZY", "ZshtncX96aKeNp4OMId9Qc73A6WZY", "TVtwnkTCroEezefsoe2LDFkXEuMZY", "37hTiYyGPbfTCMqWPLwXNd6EFtVZY", "DtjhMPr2FpFePhE776xPR7ojNB8YY", "BIPgOM4lzU9YQRHzIjSIQzrbvNeZY", "nHv1gBzhfDsEvaDnC6M9vr7CYX6YY", "3JU3JkYUigoRYlWmroMuZZxByCYZY", "HxwpFrN94rYwgwyiV6BiZHLBltAZY", "Za4LkNWcEQhD1RChbBzjTKnvxBAZY", "J4Pr54EMYdSBfzYmK6eKkWe3RaFZY", "5wVwo7peMgSMWb0dsrH9jwo9WVAZY", "h8Fmy1qzUGG4lBFGfb31SjDiUGLZY", "HB4bwMVcamVtUPQMP2MJc35FHKRZY", "lKv6rFgrdhI64fbYyy63mu1r4ZRZY", "v315OXAZGDtfwxLSPIRPfpVi4WSZY", "tQiHNX7E6UpKfjPkYomH2PsKljEZY", "rvICHCxeNK7IqvNrk0Drf85qXjPZY", "TTkKcNOlWJPRT8Wb0aHUGjLDq2SZY", "nbxpOO1LvjrrWZKZASRfKRIkthFZY", "fPLKFxrZLxSYDhjVpgkBOf3hLkBZY", "5CKy0ShlCGh9l8lDP3exJzb4srRZY", "TNt8KLJLfoxrHvEpC0V5tFnBwgRZY", "TxJXth0iSoppr2LgK1bLaD8y2uCZY", "nVSVlXHU9h7FhC045q4Gdjyqg4RZY", "hGioX64KaE6rY4YQNIqPu2B4ggCZY", "hYbAxLo83qPQzJeqOMCOMWWLCQIZY", "hU56edFX3qoNe3E5TPWrAj4U2wFZY", "NubU5iviA5Ir5jPdbQJ6s91lYmPZY", "LF3G4lLDb0ums1aN4EUQVEljEbQZY", "PFwbIJuWEF51cfkUAqavc4MOWeaZY", "LtVLKMuLQKRsNKrotojepkrKJyRZY", "Bw7ylMnvtd2OCkDElkx4bfLiCccZY", "he4ZHh9m9Io00feRKdXOf2IAT18YY", "H16fw4h4kY8UQOan651S8iJekDgZY", "Lx92gNAFSqDa0j5MYQjzT5hUWgcZY", "9kKkjzTf9uhBHtJwYpruvtp0IbTZY", "dyLd3VthX1WDTnB5vsq7Otq1KsbZY"]
#    orders = ["fdExeEeTQeznCSSmzUptN1BDhV7YY", "diN84xqVxgjgxhsud07lpgySHJXZY", "FIOEmTQoK7zqsvACE0Z5bZH0cgRZY", "N0MLbb9aemzb9wnzXs6Bku5fWMaZY", "jFd2XClzaY9Fcit8DTFM8vN15dJZY", "ZGC1CePsbt3q6D2kYy3V8ITM6u7YY", "nhSMIOJwJcU0GlH2qXrfyJ3t6SSZY", "BeMj1vFWpEaHFwAm8q2vL0Ahn2JZY", "vRWdz93SBzU8MuiREPDUjMxaSADZY", "JOY6Bqlijz7h3wMsh2KVpfaC13NZY", "hwr44NS0Clv0h3RbM4hMHaJPgY6YY", "LTclA172cCXUqqjtjoNZjnigdADZY", "P3TKNfxnCYek8qD1ENun6o5IFuVZY", "hmOCVk36HhSZ4e76ItVYUZOAK9aZY", "jxvIdSCzQCXDEUGuQBWxrw3fub7YY", "NyZOBHrsD6CQmuS5Q2sgBzo9iubZY", "rBd28h5w8Vr88PVFuNA4OMeFVxOZY", "XPTXk8CLH76tCHqh9dktc1FgEJbZY", "5IZCXhvH91GIkusEoZJHwHSkD85YY", "fRStnuBGueWib9o8DPH0nPyVbwNZY", "jB7GrGQaz8cAURhqXsFi2wCM1kHZY", "rJhWuMErAiAgaUkem6CLcHwbR5PZY", "NqXpA6Ophz5SomgYar0S5e004wCZY", "Nw67bjKryx9R1MfPOCkNrccguqTZY", "9YQCxmWMknzGdcWvpyYnzSWrZUDZY", "XDVPy6yiaVVKodMPlM2OBX5QJneZY", "tG5dPKTSjfBrRUA8OPTpyH3swuRZY", "DxBxrUwdQXeaBUp6A7EFrDckPgKZY", "XjFnKg6HhQDEJgB1v4u1VnoOtQCZY", "D9L9YcAgnrXVoXQ0skp2gVQGFBAZY", "xGm0Np5X7EYx6Vb0oJ4GBYZLhQVZY", "jL00lkbxYFWdR7neun9eFaawNXcZY", "nvXBFF6I6KOe7499BOPPHExtJmQZY", "zvo7P64KczK5RcSRIRD1NW6XfJfZY", "JAv743O2w9d0gKodOsV17s0LiYGZY", "pAnZ5uDhUxe2eD5yCCl7epZgNr8YY", "5g1SRMbZfHWFBbDMYsEN6aKoNkbZY", "hui06AnBNpMkkQmXQyNPnyXUwXWZY", "bfiz0eUq1rGy4daVEWzen2RJV8XZY", "BsBEwGrXPrLDeYzgbLBH2VIojXIZY", "z1pMaBpEaQJNe0FIqhfIBXmxHnRZY", "Ddxoix0J2EcHzn15gu9u9uRT0C6YY", "tw8YtUvEW2ID6Q8HnG6Blw6AvTBZY", "TZbenWt1jO8EdwBYmdJyDR7WVuTZY", "zzWz8WLg0DJk98IkS1jm8LzhxzcZY", "pcJjluY7LhqImg4UMVnv5VhOxQaZY", "X7tTDPrJhcefKS1jHdV3N9XScVbZY", "fLT5iFlQKDqgdaOFie7aiw2kZDGZY", "lIWEA43yK2a6MrKzCuHFIicdGRUZY", "Dl1S3Ra4oFbAeDDN7xmSOsOsTYaZY", "Xbd3l3P9EfDP1eQoeAtOU5Zpd37YY", "XfVGP1UoW3aigFxJpyrXLyWpatTZY", "Hla3uunDgcT94O4kwLROaihBdicZY", "frFycUPgfiFcUifPF3p2kV2bQSTZY", "9oq9Y3bo7FhhM1ML90BaPECookFZY", "7tdxONjadwWZ5hZbRFhdZ0DC3VSZY", "tSNmijLw3Cln2dYNyHK7YC78ATXZY", "btRRnH9JrIDHwFLvjEWE7xNiHDFZY", "738ess9QCXEpUDZMhaOF3WopmSbZY", "d86aPvVCAhgvwnkwf8fAy6lKEtTZY"]
    orders = ["vBiPNSEuEcLEOOqye8N1wZQrPTUZY"]

    orders_api = square_client.orders

    body = {
        'location_id': SQUARE_LOCATION,
        'order_ids': orders
    }

    result = orders_api.batch_retrieve_orders(body)
    if result.is_success():
        for order in result.body['orders']:
            pn = order['fulfillments'][0]['pickup_details']['recipient'].get('phone_number').replace("+1","").replace("-","")
            if pn != "":
                #print(pn)
                print(f"update orders set phone_number = '{pn}' where id = '{order['id']}';")
            else:
                print("no phone")
    else:
        print("failed: %s", result)
    print(len(orders))


if __name__ == '__main__':
    get_times()

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

    doc = build_doc_from_event(webhook_event)

    commit_to_firestore(doc)


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

    payment = webhook_event['data']['object']
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
    customer_id_ref = event_ref.collection('orders').where("customer.id", "==", customer_id)
    order_cust_ref = event_ref.collection('orders').where("order.customer_id", "==", customer_id)
    results = customer_id_ref.get()
    results.append(order_cust_ref.get())
    if len(results) == 0:
        log("received update for customer ID %s but no documents matched", customer_id)
        return

    # if yes, rebuild for each of those docs
    for result in results:
        doc = build_doc_from_event(None, order_id=result.get('order.id'), customer_id=customer_id)
        update_in_firestore(doc)


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
    if order['fulfillments'][0]['type'] == "PICKUP" and order.get('customer_id') is not None:
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

    recipient = order['fulfillments'][0]['pickup_details']['recipient']
    name_tokens = recipient['display_name'].split(" ")

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
    return order['tenders'][0]['id'] if len(order['tenders']) == 1 else None


def get_square_payment(payment_id: str):
    """ Gets Square Payment object for given id value from Square API

    Raises exception if there was any error (transient or invalid payment ID)
    """
    payments_api = square_client.payments

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
