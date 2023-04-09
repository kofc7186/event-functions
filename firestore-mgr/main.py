""" This Cloud Function is triggered on a new order document being written to Firestore.

    It reads the document and:
     - creates a label/printout for the order and stores it in GCS
     - adds a row to CloudSQL table
"""
# pylint: disable=redefined-outer-name,unused-argument,no-member

# TODO: dynamically scan Jinja2 template to extract required fields and compare
#       to changes to determine if we need to re-generate label

import copy
import contextvars
import enum
import json
import os
import re

import jinja2

from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, Float, Enum, Text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from weasyprint import HTML, CSS

from google.cloud import storage, firestore

GCS_BUCKET = os.environ['GCS_BUCKET']
GOOGLE_SHEET_URL = os.environ['GOOGLE_SHEET_URL']

# Instantiates a client
client = storage.Client()

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


class OrderState(enum.Enum):
    """ OrderState docstring """
    PLACED = 1
    ARRIVED = 2
    CANCELLED = 3


Base = declarative_base()


class Order(Base):  # pylint: disable=too-many-instance-attributes
    """ Order docstring """
    __tablename__ = 'orders'  # TODO: add event date into table name to provide separation

    id = Column(String(1024), primary_key=True)
    label_number = Column(Integer)
    square_order_number = Column(Integer)
    receipt_url = Column(Text)
    pickup_window = Column(Text)
    customer_name = Column(Text)
    last_name = Column(Text)
    phone_number = Column(Text)
    crawfish_meals = Column(Integer, default=0)
    shrimp_meals = Column(Integer, default=0)
    kids_meals = Column(Integer, default=0)
    beers = Column(Text)
    tip = Column(Float, default=0)
    total = Column(Float, default=0)
    fees = Column(Float, default=0)
    note = Column(Text, nullable=True)
    status = Column(Enum(OrderState))
    checkin_time = Column(Text, nullable=True)
    label_url = Column(Text)

    def __repr__(self):
        return f'Order {self.id} - SON {self.square_order_number} - {self.customer_name}'

    def __init__(self, doc: dict):
        self.__update_id(doc)
        self.__update_label_number(doc)
        self.__update_square_order_number(doc)
        self.__update_receipt_url(doc)
        self.__update_pickup_window(doc)
        self.__update_customer_name(doc)
        self.__update_last_name(doc)
        self.__update_phone_number(doc)
        self.__update_meals(doc)
        self.__update_beers(doc)
        self.__update_tip(doc)
        self.__update_total(doc)
        self.__update_fees(doc)
        self.__update_note(doc)
        self.__update_status(doc)
        self.__update_checkin_time(doc)

    def __update_id(self, doc):
        self.id = doc['order']['id']  # pylint: disable=invalid-name
        return False

    def __update_label_number(self, doc):
        self.label_number = doc['order_number']
        return False

    def __update_square_order_number(self, doc):
        self.square_order_number = doc['payment']['reference_id']
        return True

    def __update_receipt_url(self, doc):
        self.receipt_url = doc['payment']['receipt_url']
        return False

    def __update_pickup_window(self, doc):
        self.pickup_window = extract_pickup_time(doc['order'])
        return False

    def __update_customer_name(self, doc):
        given_name = doc['customer'].get('given_name')
        family_name = doc['customer'].get('family_name')
        if not given_name or not family_name:
            display_name = \
                doc['order']['fulfillments'][0]['pickup_details']['recipient'].get('display_name')
            if display_name:
                name_tokens = display_name.split(" ")
                given_name = " ".join(name_tokens[:-1])
                family_name = name_tokens[-1]
        self.customer_name = f"{given_name} {family_name}".title()
        return True

    def __update_last_name(self, doc):
        family_name = doc['customer'].get('family_name')
        if not family_name:
            display_name = \
                doc['order']['fulfillments'][0]['pickup_details']['recipient'].get('display_name')
            if display_name:
                name_tokens = display_name.split(" ")
                family_name = name_tokens[-1]
        self.last_name = family_name.title()
        return False

    def __update_phone_number(self, doc):
        phone_number = doc['customer'].get('phone_number')
        if not phone_number:
            phone_number = \
                doc['order']['fulfillments'][0]['pickup_details']['recipient'].get('phone_number')
        self.phone_number = phone_number.replace("+", "").replace("-", "")
        return True

    def __update_meals(self, doc):
        self.crawfish_meals, self.shrimp_meals, self.kids_meals = \
            extract_meal_counts(doc['order'])
        return True

    def __update_beers(self, doc):
        self.beers = json.dumps(extract_beers(doc['order']))
        return True

    def __update_tip(self, doc):
        self.tip = doc['order']['total_tip_money']['amount'] / 100
        return False

    def __update_total(self, doc):
        self.total = doc['order']['total_money']['amount'] / 100
        return True

    def __update_fees(self, doc):
        try:
            self.fees = doc['payment']['processing_fee'][0]['amount_money']['amount'] / 100
        except Exception as e:
            log("exception determining fees: %s", e)
        return False

    def __update_note(self, doc):
        note = doc['order'].get('note')
        if not note:
            note = doc['order']['fulfillments'][0]['pickup_details'].get('note')
        self.note = note
        return True

    def __update_status(self, doc):
        try:
            self.status = OrderState[doc['pickup']['status']]
        except Exception:
            self.status = OrderState.PLACED
        return False

    def __update_checkin_time(self, doc):
        try:
            self.checkin_time = doc['pickup']['checkin_time']
        except Exception:
            self.checkin_time = None
        return False

    update_map = {
        re.compile(r"^order.id$"): ['_Order__update_id'],
        re.compile(r"^order_number$"): ['_Order__update_label_number'],
        re.compile(r"^payment.reference_id$"): ['_Order__update_square_order_number'],
        re.compile(r"^payment.receipt_url$"): ['_Order__update_receipt_url'],
        re.compile(r"^order.line_items.*"): ['_Order__update_pickup_window',
                                             '_Order__update_meals',
                                             '_Order__update_beers'],
        re.compile(r"^order.fulfillments$"): ['_Order__update_customer_name',
                                              '_Order__update_last_name',
                                              '_Order__update_note'],
        re.compile(r"^customer.given_name$"): ['_Order__update_customer_name'],
        re.compile(r"^customer.family_name$"): ['_Order__update_customer_name',
                                                '_Order__update_last_name'],
        re.compile(r"^customer.phone_number$"): ['_Order__update_phone_number'],
        re.compile(r"^order.total_tip_money.amount$"): ['_Order__update_tip'],
        re.compile(r"^order.total_money.amount$"): ['_Order__update_total'],
        re.compile(r"^payment.processing_fee.*"): ['_Order__update_fees'],
        re.compile(r"^order.note$"): ['_Order__update_note'],
        re.compile(r"^pickup.*"): ['_Order__update_status',
                                   '_Order__update_checkin_time']
    }

    def update(self, update_mask, context):
        """ updates Python/ORM object based on field paths in update_mask """
        label_update = False

        doc = fetch_document_from_firestore(context)
        # iterate over field paths updating appropriate properties on order object
        for field_path in update_mask['fieldPaths']:
            for regex, funcs in self.update_map.items():
                if regex.match(field_path):
                    for func in funcs:
                        if getattr(self, func)(doc):
                            label_update = True

        return label_update


def extract_pickup_time(order) -> str:
    """ extracts the earliest pickup time from an order"""
    min_pickup_time = ""
    for line_item in order['line_items']:
        if (line_item['name'] == "Crawfish Boil Meal" or line_item['name'] == "Shrimp Boil Meal") \
                and line_item['variation_name']:
            if min_pickup_time == "" or line_item['variation_name'] < min_pickup_time:
                min_pickup_time = line_item['variation_name']

    if min_pickup_time == "":
        min_pickup_time = "6:00PM-6:15PM Serving"

    return min_pickup_time


def extract_meal_counts(order):
    """ This extracts the count of each type of meal (crawfish / shrimp / kids)"""
    crawfish = 0
    shrimp = 0
    kids = 0

    for line_item in order['line_items']:
        if line_item['name'] == "Crawfish Boil Meal":
            crawfish += int(line_item['quantity'])
        elif line_item['name'] == "Shrimp Boil Meal":
            shrimp += int(line_item['quantity'])
        elif line_item['name'] == "Kids Meal":
            kids += int(line_item['quantity'])

    return crawfish, shrimp, kids


def extract_beers(order):
    """ This extracts a list of KVPs of type of beer and quantity """
    beers = {}
    for line_item in order['line_items']:
        if line_item['name'] == "Brüeprint Can Beer Ticket":
            if not beers.get("Cans"):
                beers["Cans"] = 0
            beers["Cans"] += int(line_item['quantity'])
        elif line_item['name'] == "Brüeprint Draft Beer Ticket":
            if not beers.get("Draft"):
                beers["Draft"] = 0
            beers["Draft"] += int(line_item['quantity'])

    return beers


db_user = os.environ["DB_USER"]
db_pass = os.environ["DB_PASS"]
db_name = os.environ["DB_NAME"]
db_socket_dir = os.environ.get("DB_SOCKET_DIR", "/cloudsql")
instance_connection_name = os.environ["INSTANCE_CONNECTION_NAME"]
mysql_engine = create_engine(
    f'mysql+pymysql://{db_user}:{db_pass}@/{db_name}?'
    f'unix_socket={db_socket_dir}/{instance_connection_name}'
)

sheets_engine = create_engine("shillelagh://",
                              adapters=["gsheetsapi"],
                              adapter_kwargs={
                                    "gsheetsapi": {
                                        "app_default_credentials": True,
                                        "catalog": {
                                            Order.__tablename__: GOOGLE_SHEET_URL
                                        }
                                    }
                              })

mysql_sessionmaker = sessionmaker(bind=mysql_engine)
mysql_session = mysql_sessionmaker()

sheets_sessionmaker = sessionmaker(bind=sheets_engine)
sheets_session = sheets_sessionmaker()


def handle_created(data, context):
    """ This is called when a new document is added to Firestore. Unfortunately the view
        passed in under data['value'] is not easily converted to a Python dict, so we
        simply fetch the referenced doc from Firestore before proceeding. There is a small
        race condition in that we read a more up to date version of the document than was
        initially created but we take that risk knowingly here.
    """

    doc = fetch_document_from_firestore(context)

    # Create Order object
    order = Order(doc)
    ctx_id.set(order.id)

    # Create label pdf
    pdf_bytes = create_label(order)

    # Store to GCS, get URL, update order object
    order.label_url = store_label_to_gcs(pdf_bytes, order)

    sheets_order = copy.deepcopy(order)

    # Commit to mysql
    mysql_session.add(order)
    order.__table__.create(mysql_engine, checkfirst=True)
    mysql_session.commit()

    # Commit to sheets
    sheets_order.__table__.create(sheets_engine, checkfirst=True)
    sheets_session.add(sheets_order)
    sheets_session.commit()


def handle_updated(data, context):
    """ This fires when a firestore document has been updated (either manually or due to a Square
    Webhook order.updated event firing and updating our local copy)
    """
    log("handle_update entered: %s", context)

    # try fetching existing order from mysql
    order_id = data['value']['fields']['order']['mapValue']['fields']['id']['stringValue']
    ctx_id.set(order_id)

    log(f"update requested with mask {data['updateMask']}", request=data)
    order = mysql_session.query(Order).filter_by(id=order_id).one_or_none()

    if not order:
        log("requested to update a record in CloudSQL that we couldn't find")
        mysql_session.close()
        handle_created(data, context)
        return

    # recreate label pdf if needed (check for update to name, order counts, phone #, total, beers)
    if order.update(data['updateMask'], context):
        log("update requires new label to be generated")
        # Create label pdf
        pdf_bytes = create_label(order)

        # Store to GCS, get URL, update order object
        order.label_url = store_label_to_gcs(pdf_bytes, order)

    # Commit updated order to mysql
    mysql_session.commit()

    # Commit updated order to sheets
    sheets_order = sheets_session.query(Order).filter_by(id=order_id).one_or_none()
    sheets_order.update(data['updateMask'], context)
    sheets_order.label_url = order.label_url

    sheets_session.commit()


def fetch_document_from_firestore(context):
    """ this grabs the document from Firestore and returns as a Python dict """

    # extract relevant document & collection paths
    path_parts = context.resource.split('/documents/')[1].split('/')
    collection_path = path_parts[0]
    document_path = '/'.join(path_parts[1:])

    fs_client = firestore.Client()
    doc = fs_client.collection(collection_path).document(document_path)

    doc_snap = doc.get()

    if doc_snap.exists:
        return doc_snap.to_dict()

    raise KeyError(f"could not find {context.resource} in Firestore")


def create_label(order):
    """ create label for given order """
    template_loader = jinja2.FileSystemLoader(searchpath="./")
    template_env = jinja2.Environment(loader=template_loader)
    template_file = "label_template.html"
    template = template_env.get_template(template_file)

    output_text = template.render(order=order, beers=json.loads(order.beers))

    html_renderer = HTML(string=output_text)

    return html_renderer.write_pdf(stylesheets=[
        CSS('label.css'),
        "https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css"])


def store_label_to_gcs(pdf_bytes, order):
    """ writes PDF bytes to GCS bucket, naming file by:

    "last_name - square_order_number.pdf"
    """
    bucket = client.get_bucket(GCS_BUCKET)
    # create filename
    file_name = f"{os.environ['EVENT_DATE']}/{order.last_name} - {order.square_order_number}.pdf"
    log("uploading label file to GCS bucket as %s", file_name)
    blob = bucket.get_blob(file_name)
    if not blob:
        blob = bucket.blob(file_name)
    blob.upload_from_string(pdf_bytes, content_type='application/pdf')
    return blob.self_link
