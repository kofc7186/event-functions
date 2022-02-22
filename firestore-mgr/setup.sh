#!/usr/bin/env bash

gcloud functions deploy FUNCTION_NAME \
  --entry-point ENTRY_POINT \
  --runtime RUNTIME \
  --trigger-event "providers/cloud.firestore/eventTypes/document.create" \
  --trigger-resource "projects/serverless-fish-fry/databases/(default)/documents/events/2022-03-04/orders/{order}"
