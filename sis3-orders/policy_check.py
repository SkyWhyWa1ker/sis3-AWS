"""Lab policy checks; a small alternative to installing a large policy tool."""
from pathlib import Path
import yaml


class Loader(yaml.SafeLoader):
    pass


def intrinsic(loader, tag, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
    else:
        value = loader.construct_mapping(node)
    return {tag: value}


Loader.add_multi_constructor("!", intrinsic)


def require(condition, message):
    if not condition:
        raise SystemExit("POLICY FAILED: " + message)


app = yaml.load(Path("infra/app.yaml").read_text(), Loader=Loader)
registry = yaml.load(Path("infra/registry.yaml").read_text(), Loader=Loader)
r = app["Resources"]
require(not any(x["Type"] == "AWS::EC2::NatGateway" for x in r.values()), "No NAT gateways in this lab")
for key in ("OrdersQueue", "DeadLetterQueue"):
    require(r[key]["Properties"].get("SqsManagedSseEnabled") is True, f"{key} encryption")
require(r["OrdersTable"]["Properties"]["SSESpecification"]["SSEEnabled"] is True, "Table encryption")
require(r["Logs"]["Properties"]["RetentionInDays"] == 7, "Seven-day log retention")
require(r["OrdersQueue"]["Properties"]["RedrivePolicy"]["maxReceiveCount"] == 3, "DLQ redrive count")
require(r["TaskDefinition"]["Properties"]["TaskRoleArn"] != r["TaskDefinition"]["Properties"]["ExecutionRoleArn"], "Separate task/execution roles")
require(r["Service"]["Properties"]["DeploymentConfiguration"]["DeploymentCircuitBreaker"] == {"Enable": True, "Rollback": True}, "Deployment rollback")
repo = registry["Resources"]["Repository"]["Properties"]
require(repo["ImageTagMutability"] == "IMMUTABLE", "Immutable ECR tags")
require("LifecyclePolicy" in repo, "ECR lifecycle policy")
print("Lab policy checks passed (encryption, roles, DLQ, logs, rollback, ECR, no NAT).")
