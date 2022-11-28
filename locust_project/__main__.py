import pulumi
import pulumi_gcp as gcp

# Get the configuration settings from the Pulumi stack
config = pulumi.Config()
NODE_COUNT = config.get_int('gke_node_count')
MACHINE_TYPE = config.get('gke_machine_type')


# Create a project for the Locust cluster
bench_project = gcp.organizations.Project(
    'project',
    name='pulumi-gke',
    project_id='loucust-cluster-gke-231120253',
    billing_account='01659C-EF5CED-1C5E4B',
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
