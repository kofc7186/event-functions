#!/usr/bin/env bash

# TODO: create blank spreadsheet
# TODO: set environment variables
# TODO: setup cloudSQL, create database for event_date

gcloud functions deploy firestore-mgr-created \
  --region us-east1 \
  --entry-point handle_created \
  --env-vars-file .env.yaml \
  --runtime python39 \
  --memory=256MB \
  --trigger-event "providers/cloud.firestore/eventTypes/document.create" \
  --trigger-resource "projects/serverless-fish-fry/databases/(default)/documents/events/2022-03-04/orders/{order}"

gcloud functions deploy firestore-mgr-updated \
  --region us-east1 \
  --entry-point handle_updated \
  --env-vars-file .env.yaml \
  --runtime python39 \
  --memory=256MB \
  --trigger-event "providers/cloud.firestore/eventTypes/document.update" \
  --trigger-resource "projects/serverless-fish-fry/databases/(default)/documents/events/2022-03-04/orders/{order}"
