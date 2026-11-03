# Assignment 2, advanced: Minikube deployment, scaling and self-healing

| Claim | Evidence |
|---|---|
| Whole application deployed with Kubernetes Deployments and Services | `01_deploy.txt`: 11 pods Running (3 MySQL, 2 toll-transaction, 2 wallet, 2 vehicle-registry, notification, mock-bank) |
| Main workflow works through Kubernetes, not just pods Running | `02_workflow_on_k8s.txt`: `scripts/e2e_test.py` 18 of 18 checks pass through the cluster Services |
| Self-healing | `03_self_healing.txt`: a toll-transaction pod is deleted; the Deployment creates a replacement within 3 s; 52 of 52 requests made through the Service during the deletion return 200 |
| Scaling | `04_scaling.txt`: vehicle-registry scaled 2 to 4; 20 in-cluster requests are spread over all four pods (3/6/6/5); scaled back to 2 |
| Idempotency holds across replicas | `05_idempotency_two_replicas.txt`: 20 simultaneous identical crossings, split 9/11 over both toll-transaction pods, create one crossing (19 replays), because the key store is in MySQL and not in a pod's memory |

Note learned during the self-healing test: `kubectl port-forward svc/...` attaches to one pod, so a port-forward breaks when that pod is deleted. Traffic that goes through the Service inside the cluster, which is how the services call each other, is not affected. The in-cluster measurement is the evidence.
