#!/usr/bin/env bash

# list of GCP artifacts we need created
# pub/sub topics:
#  - square.order.created
#  - square.order.updated
#  - print-queue #TODO: check this name

# firestore:

# cloud SQL instance (mySQL)

# datastream

# GCS buckets (labels, datastream changes)

# TODO: add .github/workflows/function.{yml|sh}
# - this script can simply walk all dirs and run .sh
# - 
