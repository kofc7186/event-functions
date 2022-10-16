#!/usr/bin/env bash

gcloud pubsub topics create projects/serverless-fish-fry/topics/square.order.created
gcloud pubsub topics create projects/serverless-fish-fry/topics/square.order.updated

gcloud functions deploy square-webhook \
  --region us-east1 \
  --entry-point handle_webhook \
  --runtime python39 \
  --env-vars-file .env.yaml \
  --trigger-http \
  --allow-unauthenticated \
  --memory=128MB

