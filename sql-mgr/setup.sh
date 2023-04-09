#!/usr/bin/env bash

gcloud functions deploy print --region us-east1 --entry-point handle_print \
  --env-vars-file .env.yaml --runtime python311 --memory=128MB --trigger-http --allow-unauthenticated
