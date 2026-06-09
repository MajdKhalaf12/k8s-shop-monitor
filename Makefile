.PHONY: build images helm-repos k8s k8s-apps test clean status check-cluster grafana-dashboard

export KUBECONFIG ?= $(HOME)/.kube/config-os2

build images:
	docker build --platform linux/arm64 -t os2-webapp:latest ./webapp
	docker build --platform linux/arm64 -t os2-classifier:latest ./classifier
	docker build --platform linux/arm64 -t os2-traffic:latest ./traffic

helm-repos:
	helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
	helm repo add jetstack https://charts.jetstack.io 2>/dev/null || true
	helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx 2>/dev/null || true
	helm repo update

check-cluster:
	@kubectl cluster-info >/dev/null 2>&1 || (echo "kubectl cannot reach cluster. See README Step 2: export KUBECONFIG=~/.kube/config-os2" && exit 1)

k8s: check-cluster helm-repos build images
	kubectl apply -f k8s/namespaces.yaml
	@echo "Traefik: must be disabled permanently on VM1 (INSTALLATION.md Step 4a). Deleting leftovers..."
	kubectl delete helmchart traefik traefik-crd -n kube-system --ignore-not-found
	kubectl delete pod -n kube-system -l app.kubernetes.io/name=traefik --ignore-not-found
	kubectl delete daemonset -n kube-system -l svccontroller.k3s.cattle.io/svcname=traefik --ignore-not-found
	helm upgrade --install cert-manager jetstack/cert-manager \
		-n cert-manager --create-namespace --set crds.enabled=true --wait
	kubectl apply -f k8s/cert-manager/clusterissuer.yaml
	helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
		-n ingress-nginx --create-namespace \
		-f k8s/nginx-ingress/values.yaml --wait
	kubectl apply -k .
	kubectl wait --for=condition=Ready certificate/webapp-tls -n apps --timeout=120s 2>/dev/null || true
	kubectl rollout status deployment/webapp -n apps --timeout=180s || true
	kubectl rollout status deployment/traffic -n apps --timeout=120s || true
	helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
		-n monitoring --create-namespace -f k8s/monitoring/values-prom-stack.yaml
	kubectl apply -k k8s/monitoring/
	kubectl create configmap grafana-dashboard-os2 \
		--from-file=os2-overview.json=k8s/monitoring/os2-overview.json \
		-n monitoring --dry-run=client -o yaml | kubectl apply -f -
	kubectl label configmap grafana-dashboard-os2 -n monitoring \
		grafana_dashboard=1 release=kube-prometheus-stack --overwrite
	@echo "Grafana: kubectl port-forward -n monitoring svc/kube-prometheus-stack-grafana 3000:80"
	@echo "App: https://operating-systems.com  (add 192.168.28.131 operating-systems.com to /etc/hosts)"

k8s-apps: check-cluster build images
	kubectl apply -f k8s/namespaces.yaml
	kubectl apply -k .

test: build
	docker run --rm os2-classifier:latest pytest tests/ -v

clean: check-cluster
	helm uninstall kube-prometheus-stack -n monitoring 2>/dev/null || true
	helm uninstall ingress-nginx -n ingress-nginx 2>/dev/null || true
	helm uninstall cert-manager -n cert-manager 2>/dev/null || true
	kubectl delete namespace apps monitoring cert-manager ingress-nginx --ignore-not-found

status: check-cluster
	kubectl get pods -A
	kubectl get svc -n apps
	kubectl get ingress -n apps
	kubectl get hpa -n apps

grafana-dashboard: check-cluster
	kubectl create configmap grafana-dashboard-os2 \
		--from-file=os2-overview.json=k8s/monitoring/os2-overview.json \
		-n monitoring --dry-run=client -o yaml | kubectl apply -f -
	kubectl label configmap grafana-dashboard-os2 -n monitoring \
		grafana_dashboard=1 release=kube-prometheus-stack --overwrite
	@echo "Dashboard updated — refresh Grafana (or reopen OS2 Stack Overview)"
