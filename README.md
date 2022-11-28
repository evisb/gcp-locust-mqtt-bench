# gcp-locust-mqtt-bench

A benchmarking tool for testing the performance of MQTT brokers under load on GCP.


## Prerequisites
In order to run this tool, you need to have the following:
* A Google Cloud Platform account
* Google Cloud SDK installed
* Pulumi CLI installed
* Python 3.7 or higher

## Setup
* curl -fsSL https://get.pulumi.com/ | sh
* pulumi login --local (to use local filesystem state)
* pulumi login gs://<my-pulumi-state-bucket> (to use GCS bucket state)
* Migrating betwwen state backends https://www.pulumi.com/docs/intro/concepts/state/#migrating-between-state-backends
* gcloud auth application-default login (to authenticate with GCP)
* pulumi config set gcp:project your-gcp-project-id (to set the GCP project via Pulumi) or export GOOGLE_PROJECT=your-gcp-project-id (to set the GCP project via environment variable)
* pulumi config set gcp:zone us-central1-a (to set the GCP zone via Pulumi) or export GOOGLE_ZONE=europe-west1-b (to set the GCP zone via environment variable)
* pulumi config set gcp:region us-central1 (to set the GCP region via Pulumi) or export GOOGLE_REGION=europe-west1 (to set the GCP region via environment variable)
* pulumi config set gke_node_count 20 (to set the number of GKE nodes via Pulumi) or export GKE_NODE_COUNT=20 (to set the number of GKE nodes via environment variable)
* pulumi config set gke_node_machine_type e2-medium (to set the GKE node machine type via Pulumi) or export GKE_NODE_MACHINE_TYPE=e2-medium (to set the GKE node machine type via environment variable)

* pulumi up (to deploy the infrastructure)
* pulumi stack output locust_ip (to get the IP address of the locust address)
* pulumi destroy (to destroy the infrastructure)
* pulumi stack rm dev (to remove the stack)