import pulumi
import pulumi_gcp as gcp
import pulumi_docker as docker

# Create a Docker image and push it to a GCR registry.
image_name = "locust_farm"
image = docker.Image(
    build=docker.DockerBuild(context="DockerfileMaster"),
    image_name="gcr.io/locust-project/locust_farm:latest",
)