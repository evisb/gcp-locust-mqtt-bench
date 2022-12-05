from pulumi import Config, export, Output, ResourceOptions

from pulumi_gcp import projects, organizations, compute, serviceaccount
from pulumi_gcp.config import project, zone
from pulumi_gcp.container import Cluster, NodePoolNodeConfigArgs

from pulumi_docker import Image, DockerBuild

from pulumi_kubernetes import Provider
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.core.v1 import ContainerArgs, PodSpecArgs, PodTemplateSpecArgs, EnvVarArgs, ContainerPortArgs, \
                                        ProbeArgs, HTTPGetActionArgs, Service, ServicePortArgs, ServiceSpecArgs
from pulumi_kubernetes.meta.v1 import LabelSelectorArgs, ObjectMetaArgs

# Get the configuration settings from the Pulumi stack
config = Config()
NODE_COUNT = config.get_int('gke_node_count')
MACHINE_TYPE = config.get('gke_machine_type')
BILLING_ACCOUNT = config.get('billing_account')
PROJECT_NAME = config.get('project_name')
PROJECT_ID = config.get('project_id')

# Create a project for the Locust cluster
bench_project = organizations.Project(
    'locust-project',
    name=PROJECT_NAME,
    project_id=PROJECT_ID,
    billing_account=BILLING_ACCOUNT,
)

# Export the project ID, name, and number
export('project_id', bench_project.project_id)
export('project_name', bench_project.name)
export('project_number', bench_project.number)

# Enable the necessary APIs
compute_api = projects.Service('compute-api',
                               project=bench_project.project_id,
                               service='compute.googleapis.com',
                               disable_dependent_services=True)

container_api = projects.Service('container-api',
                                 project=bench_project.project_id,
                                 service='container.googleapis.com',
                                 disable_dependent_services=True)

iam_api = projects.Service('iam-api',
                           project=bench_project.project_id,
                           service='iam.googleapis.com',
                           disable_dependent_services=True)


org_api = projects.Service('org-api',
                           project=bench_project.project_id,
                           service='orgpolicy.googleapis.com',
                           disable_dependent_services=True)

registry_api = projects.Service('registry-api',
                                project=bench_project.project_id,
                                service='containerregistry.googleapis.com',
                                disable_dependent_services=True)

# Create a default VPC network
vpc = compute.Network('defaultvpc', name="default", mtu=1460, auto_create_subnetworks=True,
                      routing_mode='GLOBAL', project=bench_project.project_id,
                      opts=ResourceOptions(depends_on=[compute_api])
                      )

# Argolis specific
os_login = projects.OrganizationPolicy("compute.requireOsLogin",
                                       boolean_policy=projects.OrganizationPolicyBooleanPolicyArgs(
                                           enforced=False,
                                       ),
                                       constraint="compute.requireOsLogin",
                                       project=bench_project.project_id,
                                       opts=ResourceOptions(
                                           depends_on=[org_api])
                                       )

shielded_vm = projects.OrganizationPolicy("compute.requireShieldedVm",
                                          boolean_policy=projects.OrganizationPolicyBooleanPolicyArgs(
                                              enforced=False,
                                          ),
                                          constraint="compute.requireShieldedVm",
                                          project=bench_project.project_id,
                                          opts=ResourceOptions(
                                              depends_on=[org_api])
                                          )

vm_can_ip_forward = projects.OrganizationPolicy("compute.vmCanIpForward",
                                                list_policy=projects.OrganizationPolicyListPolicyArgs(
                                                    allow=projects.OrganizationPolicyListPolicyAllowArgs(
                                                        all=True)
                                                ),
                                                constraint="compute.vmCanIpForward",
                                                project=bench_project.project_id,
                                                opts=ResourceOptions(
                                                    depends_on=[org_api])
                                                )

vm_external_ip_access = projects.OrganizationPolicy("compute.vmExternalIpAccess",
                                                    list_policy=projects.OrganizationPolicyListPolicyArgs(
                                                        allow=projects.OrganizationPolicyListPolicyAllowArgs(
                                                            all=True)
                                                    ),
                                                    constraint="compute.vmExternalIpAccess",
                                                    project=bench_project.project_id,
                                                    opts=ResourceOptions(
                                                        depends_on=[org_api])
                                                    )

restrict_vpc_peering = projects.OrganizationPolicy("compute.restrictVpcPeering",
                                                   list_policy=projects.OrganizationPolicyListPolicyArgs(
                                                       allow=projects.OrganizationPolicyListPolicyAllowArgs(
                                                           all=True)
                                                   ),
                                                   constraint="compute.restrictVpcPeering",
                                                   project=bench_project.project_id,
                                                   opts=ResourceOptions(
                                                       depends_on=[org_api])
                                                   )

# Create a service account with the container.nodeServiceAccount role to create the GKE cluster
locust_service_account = serviceaccount.Account('ltk-sa',
                                                account_id='ltk-sa',
                                                display_name='GKE Service Account',
                                                opts=ResourceOptions(
                                                    depends_on=[iam_api]))

projects.IAMMember('node-sa-role',
                   member=locust_service_account.email.apply(
                       lambda email: f'serviceAccount:{email}'),
                   role='roles/container.nodeServiceAccount',
                   project=bench_project.project_id)

# Create a GKE cluster.
gke_cluster = Cluster("locust-cluster",
                      initial_node_count=NODE_COUNT,
                      network=vpc.name,
                      project=bench_project.project_id,
                      node_config=NodePoolNodeConfigArgs(
                          machine_type=MACHINE_TYPE,
                          service_account=locust_service_account.email,
                          oauth_scopes=[
                              'https://www.googleapis.com/auth/compute',
                              'https://www.googleapis.com/auth/devstorage.read_only',
                              'https://www.googleapis.com/auth/logging.write',
                              'https://www.googleapis.com/auth/monitoring'
                          ],
                      ),
                      opts=ResourceOptions(
                          depends_on=[container_api, os_login, shielded_vm, vm_can_ip_forward,
                                      vm_external_ip_access, restrict_vpc_peering]
                      )
                      )

# Create a GKE-style Kubeconfig to use gcloud for cluster authentication (rather than using the client cert/key directly).
gke_info = Output.all(
    gke_cluster.name, gke_cluster.endpoint, gke_cluster.master_auth)
gke_config = gke_info.apply(
    lambda info: """apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: {0}
    server: https://{1}
  name: {2}
contexts:
- context:
    cluster: {2}
    user: {2}
  name: {2}
current-context: {2}
kind: Config
preferences: {{}}
users:
- name: {2}
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: gke-gcloud-auth-plugin
      installHint: Install gke-gcloud-auth-plugin for use with kubectl by following
        https://cloud.google.com/blog/products/containers-kubernetes/kubectl-auth-changes-in-gke
      provideClusterInfo: true
""".format(info[2]['cluster_ca_certificate'], info[1], '{0}_{1}_{2}'.format(project, zone, info[0])))

# Make a Kubernetes provider instance that uses our cluster from above.
gke_provider = Provider('gke_k8s', kubeconfig=gke_config)

# Export the cluster name and endpoint.
export('cluster_name', gke_cluster.name)
export('cluster_endpoint', gke_cluster.endpoint)


# Create a Docker image for the Locust master and push it to the default GCR registry.
master = Image(name="locustMaster",
              build=DockerBuild(context="k8s", dockerfile='k8s/DockerfileMaster'),
              image_name=bench_project.project_id.apply(lambda project_id: f"gcr.io/{project_id}/locust-master:latest"),
              opts=ResourceOptions(depends_on=[registry_api]))

# Create deployment and service for the Locust master.
deployment = Deployment(
    "locust-master",
    spec=DeploymentSpecArgs(selector=LabelSelectorArgs(match_labels={
        "component": "master", }),
        replicas=1,
        template=PodTemplateSpecArgs(metadata=ObjectMetaArgs(labels={
            "app": "locust",
            "component": "master",
        }),
            spec=PodSpecArgs(containers=[
                ContainerArgs(name="locust",
                              image=master.image_name,
                              env=[EnvVarArgs(
                                  name="LOCUST_MODE",
                                  value="master",)],
                              ports=[ContainerPortArgs(name="loc-master-web", container_port=8089, protocol="TCP",),
                                     ContainerPortArgs(
                                         name="loc-master-p1", container_port=5557, protocol="TCP",),
                                     ContainerPortArgs(name="loc-master-p2", container_port=5558, protocol="TCP",), ],
                              liveness_probe=ProbeArgs(http_get=HTTPGetActionArgs(
                                  path="/", port=8089,), period_seconds=30,),
                              readiness_probe=ProbeArgs(http_get=HTTPGetActionArgs(
                                  path="/", port=8089,), period_seconds=30,)
                              ), ],),),),
    opts=ResourceOptions(
        provider=gke_provider,
        depends_on=[registry_api, master, gke_cluster]
    )
)

service = Service("locust-master",
                  metadata=ObjectMetaArgs(labels=deployment.spec.apply(
                      lambda spec: spec.template.metadata.labels),),
                  spec=ServiceSpecArgs(type="LoadBalancer", ports=[ServicePortArgs(port=8089, target_port=8089,)],
                                       selector=deployment.spec.apply(lambda spec: spec.template.metadata.labels),),
                  opts=ResourceOptions(provider=gke_provider, depends_on=[deployment]))

# Save the service IP.
locust_service_ip = Output.all(service.status).apply(
    lambda status: status[0]['load_balancer']['ingress'][0]['ip'])

ip = locust_service_ip.apply(lambda v: f"{v}")

# export the service IP 
export('locust_service_ip', ip)

# Replace the placeholder in the DockerfileWorker.template with the service IP of the master.
# Create a Docker image for the Locust worker and push it to the default GCR registry.
with open("k8s/DockerfileWorker.template", "r") as f:
    dockerfile = f.read().replace("${masterIP}", "35.184.157.78")
with open("k8s/Dockerfile", "w") as f:
    f.write(dockerfile)

worker = Image(name="locustWorker",
              build=DockerBuild(context="k8s"),
              image_name=bench_project.project_id.apply(lambda project_id: f"gcr.io/{project_id}/locust-worker:latest"),
              opts=ResourceOptions(depends_on=[registry_api]))

# Create deployment for the Locust worker.
deployment = Deployment(
    "locust-worker",
    spec=DeploymentSpecArgs(selector=LabelSelectorArgs(match_labels={
        "component": "worker", }),
        replicas=1,
        template=PodTemplateSpecArgs(metadata=ObjectMetaArgs(labels={
            "app": "locust",
            "component": "worker",
        }),
            spec=PodSpecArgs(containers=[
                ContainerArgs(name="locust",
                                image=worker.image_name,
                                env=[EnvVarArgs(
                                    name="LOCUST_MODE",
                                    value="worker",)],
                                ports=[ContainerPortArgs(name="loc-worker-web", container_port=8089, protocol="TCP",),
                                        ContainerPortArgs(
                                            name="loc-worker-p1", container_port=5557, protocol="TCP",),
                                        ContainerPortArgs(name="loc-worker-p2", container_port=5558, protocol="TCP",), ],
                                liveness_probe=ProbeArgs(http_get=HTTPGetActionArgs(
                                    path="/", port=8089,), period_seconds=30,),
                                readiness_probe=ProbeArgs(http_get=HTTPGetActionArgs(
                                    path="/", port=8089,), period_seconds=30,)
                                ), ],),),),
    opts=ResourceOptions(
        provider=gke_provider,
        depends_on=[registry_api, worker, gke_cluster]
    )
)

