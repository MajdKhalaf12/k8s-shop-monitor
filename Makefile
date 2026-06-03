.PHONY: dev down k8s k8s-apps certs flood test clean status build images helm-repos

COMPOSE := docker compose -f docker-compose.dev.yml
K8S_NS := apps monitoring cert-manager

build images:
	docker build -t os2-webapp:latest ./webapp
	docker build -t os2-apache:latest ./apache
	docker build -t os2-classifier:latest ./classifier
	docker build -t os2-traffic:latest ./traffic
	-docker tag os2-webapp:latest os2-hw2-dev-webapp1:latest 2>/dev/null || true

certs:
	chmod +x scripts/generate-certs.sh
	./scripts/generate-certs.sh

dev: certs build
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down -v

helm-repos:
	helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
	helm repo add jetstack https://charts.jetstack.io 2>/dev/null || true
	helm repo update

k8s: helm-repos build images
	kubectl apply -f k8s/namespaces.yaml
	helm upgrade --install cert-manager jetstack/cert-manager \
		-n cert-manager --create-namespace --set crds.enabled=true --wait
	kubectl apply -f k8s/cert-manager/clusterissuer.yaml
	kubectl apply -f k8s/cert-manager/certificate.yaml
	kubectl wait --for=condition=Ready certificate/apache-tls -n apps --timeout=120s 2>/dev/null || true
	kubectl apply -k .
	kubectl rollout status deployment/apache -n apps --timeout=180s || true
	helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
		-n monitoring --create-namespace -f k8s/monitoring/values-prom-stack.yaml
	kubectl apply -k k8s/monitoring/
	kubectl create configmap grafana-dashboard-os2 \
		--from-file=os2-overview.json=monitoring/grafana/dashboards/os2-overview.json \
		-n monitoring --dry-run=client -o yaml | kubectl apply -f -
	kubectl label configmap grafana-dashboard-os2 -n monitoring \
		grafana_dashboard=1 release=kube-prometheus-stack --overwrite
	@echo "Grafana: kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80"
	@echo "App: https://operating-systems.com  (run ./scripts/setup-hosts.sh first)"

k8s-apps: build images
	kubectl apply -f k8s/namespaces.yaml
	kubectl apply -k .

flood:
	$(COMPOSE) --profile traffic run --rm traffic

flood-k8s:
	kubectl delete job locust-flood -n apps --ignore-not-found
	kubectl apply -f k8s/traffic/job-flood.yaml
	kubectl wait --for=condition=complete job/locust-flood -n apps --timeout=120s || kubectl logs -n apps job/locust-flood

test: build
	docker run --rm os2-classifier:latest pytest tests/ -v 2>/dev/null || \
	docker run --rm os2-hw2-dev-classifier:latest pytest tests/ -v

clean:
	$(COMPOSE) down -v --rmi local 2>/dev/null || true
	helm uninstall kube-prometheus-stack -n monitoring 2>/dev/null || true
	helm uninstall cert-manager -n cert-manager 2>/dev/null || true
	kubectl delete namespace apps monitoring cert-manager --ignore-not-found

status:
	kubectl get pods -A
	kubectl get svc -n apps
