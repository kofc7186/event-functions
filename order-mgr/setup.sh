#!/usr/bin/env bash

gcloud functions deploy order-mgr-order-created --region us-east1 --entry-point handle_order_created --runtime python310 --env-vars-file .env.yaml --trigger-topic square.order.created --memory=128MB

gcloud functions deploy order-mgr-order-updated --region us-east1 --entry-point handle_order_updated --runtime python310 --env-vars-file .env.yaml --trigger-topic square.order.updated --memory=128MB

gcloud functions deploy order-mgr-payment-updated --region us-east1 --entry-point handle_payment_updated --runtime python310 --env-vars-file .env.yaml --trigger-topic square.payment.updated --memory=128MB

gcloud functions deploy order-mgr-customer-updated --region us-east1 --entry-point handle_customer_updated --runtime python310 --env-vars-file .env.yaml --trigger-topic square.customer.updated --memory=128MB

