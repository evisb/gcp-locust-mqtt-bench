import pulumi
import pulumi_gcp as gcp
import pulumi_docker as docker
import pulumi_kubernetes as kube

# Get the configuration settings from the Pulumi stack
config = pulumi.Config()
NODE_COUNT = config.get_int('gke_node_count')
MACHINE_TYPE = config.get('gke_machine_type')
BILLING_ACCOUNT = config.get('billing_account')
PROJECT_NAME = config.get('project_name')
PROJECT_ID = config.get('project_id')


# Create a project for the Locust cluster
bench_project = gcp.organizations.Project(
    'locust-project',
    name=PROJECT_NAME,
    project_id=PROJECT_ID,
    billing_account=BILLING_ACCOUNT,
)

# Export the project ID, name, and number
pulumi.export('project_id', bench_project.project_id)
pulumi.export('project_name', bench_project.name)
pulumi.export('project_number', bench_project.number)

# Enable the necessary APIs
compute_api = gcp.projects.Service(
    'compute-api',
    project=bench_project.project_id,
    service='compute.googleapis.com',
).disable_dependent_services

container_api = gcp.projects.Service(
    'container-api',
    project=bench_project.project_id,
    service='container.googleapis.com',
).disable_dependent_services

org_api = gcp.projects.Service(
    'org-api',
    project=bench_project.project_id,
    service='orgpolicy.googleapis.com',
).disable_dependent_services

registry_api = gcp.projects.Service(
    'registry-api',
    project=bench_project.project_id,
    service='containerregistry.googleapis.com',
).disable_dependent_services

# Create a default VPC network
vpc = gcp.compute.Network('default', mtu=1460, auto_create_subnetworks=True,
                          routing_mode='GLOBAL', project=bench_project.project_id,
                          opts=pulumi.ResourceOptions(depends_on=[compute_api])
                          )

# Create a firewall rule to allow ingress traffic


# Argolis specific

os_login = gcp.projects.OrganizationPolicy(
    "compute.requireOsLogin",
    boolean_policy=gcp.projects.OrganizationPolicyBooleanPolicyArgs(
        enforced=False,
    ),
    constraint="compute.requireOsLogin",
    project=bench_project.project_id,
    opts=pulumi.ResourceOptions(depends_on=[org_api])
)

shielded_vm = gcp.projects.OrganizationPolicy(
    "compute.requireShieldedVm",
    boolean_policy=gcp.projects.OrganizationPolicyBooleanPolicyArgs(
        enforced=False,
    ),
    constraint="compute.requireShieldedVm",
    project=bench_project.project_id,
    opts=pulumi.ResourceOptions(depends_on=[org_api])
)

vm_can_ip_forward = gcp.projects.OrganizationPolicy(
    "compute.vmCanIpForward",
    list_policy=gcp.projects.OrganizationPolicyListPolicyArgs(
        allow=gcp.projects.OrganizationPolicyListPolicyAllowArgs(
            all=True)
    ),
    constraint="compute.vmCanIpForward",
    project=bench_project.project_id,
    opts=pulumi.ResourceOptions(depends_on=[org_api])
)

vm_external_ip_access = gcp.projects.OrganizationPolicy(
    "compute.vmExternalIpAccess",
    list_policy=gcp.projects.OrganizationPolicyListPolicyArgs(
        allow=gcp.projects.OrganizationPolicyListPolicyAllowArgs(
            all=True)
    ),
    constraint="compute.vmExternalIpAccess",
    project=bench_project.project_id,
    opts=pulumi.ResourceOptions(depends_on=[org_api])
)

restrict_vpc_peering = gcp.projects.OrganizationPolicy(
    "compute.restrictVpcPeering",
    list_policy=gcp.projects.OrganizationPolicyListPolicyArgs(
        allow=gcp.projects.OrganizationPolicyListPolicyAllowArgs(
            all=True)
    ),
    constraint="compute.restrictVpcPeering",
    project=bench_project.project_id,
    opts=pulumi.ResourceOptions(depends_on=[org_api])
)


# Create a GKE cluster.
gke_cluster = gcp.container.Cluster(
    "locust-cluster",
    initial_node_count=NODE_COUNT,
    network=vpc.name,
    project=bench_project.project_id,
    node_config=gcp.container.NodePoolNodeConfigArgs(
        machine_type=MACHINE_TYPE,
    ),
    opts=pulumi.ResourceOptions(
        depends_on=[container_api, os_login, shielded_vm, vm_can_ip_forward,
                    vm_external_ip_access, restrict_vpc_peering]
    )
)

# Export the cluster name and endpoint.
pulumi.export('cluster_name', gke_cluster.name)
pulumi.export('cluster_endpoint', gke_cluster.endpoint)

'''
pulumi.export('firewall_rule', gcp.compute.Firewall('default-allow-locust', network=vpc.name, allows=[
        gcp.compute.FirewallAllowArgs(
            protocol="http",
        )]))

# update firewall rule to allow ingress traffic from the locust master

'''

# Create a Docker image and push it to the default GCR registry.
image = docker.Image(
    name="DockerfileMaster",
    build=docker.DockerBuild(context="k8s"),
    image_name="gcr.io/locust-cluster-gke-23112j/locust_master:latest",
)