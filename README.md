# Dell PowerVault ME5 SSH Prometheus exporter

The exporter connects to the ME5 CLI over SSH, executes `show ...` commands, parses XML responses, and exposes Prometheus metrics on port 9824.

## Architecture

```text
collector/
  ssh.py
  xml.py
collectors/
  alerts.py
  controllers.py
  disks.py
  pools.py
  ports.py
  system.py
  volumes.py
config.py
metrics.py
me5_exporter.py
```

Each collector runs independently. If one command or parser fails, the exporter logs the exception, marks only that collector as down, and continues with the remaining collectors over the same SSH session.

## Start

```bash
cp .env.example .env
# edit credentials
docker compose up -d --build
curl http://127.0.0.1:9824/metrics
```

The SSH host key is accepted on first use and persisted in the `me5-known-hosts` volume. To reset it:

```bash
docker compose down
docker volume rm me5_exporter_full_me5-known-hosts
```

## Implemented collectors

- `show system`
- `show controllers`
- `show disks`
- `show pools`
- `show volumes`
- `show alerts`
- `show host-ports`
- `show expander-ports`

Each collector can be disabled with `ENABLE_<NAME>=false`.

## Important

Controller parsing is validated against ME5 XML output. Disk, pool, volume, and alert property names can differ by firmware. Collector-specific failures do not stop the exporter; inspect:

- `dell_me_collector_up{collector="..."}`
- `dell_me_collector_errors_total{collector="..."}`
- container logs

## Prometheus scrape config

```yaml
scrape_configs:
  - job_name: dell-me5
    static_configs:
      - targets: ['monitoring-host:9824']
```
