# NVIDIA Infra Observabilidade

Stack de observabilidade da infraestrutura Docker e da GPU NVIDIA, provisionada integralmente com Ansible.

## Componentes

- Grafana: dashboard em `http://HOST:3000`
- Prometheus: somente localhost em `127.0.0.1:9090`
- Node Exporter: CPU, RAM, filesystem, rede e load average
- cAdvisor: containers Docker
- NVIDIA DCGM Exporter: utilização, temperatura, memória e potência da GPU

## Deploy

```bash
ansible-playbook -i ansible/inventory.ini ansible/site.yml \
  -e ansible_user=getter -e observability_grafana_admin_password='troque-esta-senha'
```

O playbook é idempotente e instala a stack em `/home/getter/nvidia-infra-observabilidade`. A senha do Grafana deve ser fornecida por Ansible Vault ou variável de ambiente, nunca versionada.

## Verificação

```bash
docker compose -f /opt/nvidia-infra-observabilidade/compose/docker-compose.yml ps
curl http://127.0.0.1:9090/-/ready
curl http://127.0.0.1:3000/api/health
```

## Segurança

Não são armazenadas credenciais neste repositório. Prometheus e exporters não são publicados na rede. O Grafana exige autenticação.
