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
  versions.py
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

If a previous container created the volume with root-owned permissions and the exporter logs `chmod: changing permissions of '/app/.ssh': Operation not permitted`, reset the volume once and rebuild:

```bash
docker compose down -v
docker compose up -d --build
```

## Implemented collectors

- `show system`
- `show controllers`
- `show disks`
- `show pools`
- `show volumes`
- `show alerts`
- `show events`
- `show ports`
- `show sas-link-health` when `ENABLE_EXPANDER_PORTS=true` and `EXPANDER_PORTS_INTERVAL` has elapsed
- `show network-parameters` when `ENABLE_MANAGEMENT_PORTS=true` and `MANAGEMENT_PORTS_INTERVAL` has elapsed
- `show versions detail`

Each collector can be disabled with `ENABLE_<NAME>=false`.

The ports collector always runs `show ports` for host ports. Expansion and management port sub-commands can be controlled separately:

- `ENABLE_EXPANDER_PORTS=false` skips `show sas-link-health`.
- `EXPANDER_PORTS_INTERVAL=600` runs `show sas-link-health` at most once every 600 seconds and keeps the last exported values between runs. This is useful when no expansion enclosure is connected and the command is slow.
- `ENABLE_MANAGEMENT_PORTS=false` skips `show network-parameters`.
- `MANAGEMENT_PORTS_INTERVAL=60` runs `show network-parameters` at most once every 60 seconds.

## Important

Controller parsing is validated against ME5 XML output. Disk, pool, volume, and alert property names can differ by firmware. Collector-specific failures do not stop the exporter; inspect:

- `dell_me_collector_up{collector="..."}`
- `dell_me_collector_errors_total{collector="..."}`
- container logs

Alert metrics count only unresolved alerts. Resolved alert history from `show alerts` is ignored.

## Metrics

Boolean health/status metrics use `1` for OK/true/up and `0` for not OK/false/down or unknown.

### Exporter

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `dell_me_exporter_up` | gauge | - | `1` when the last collection cycle established an SSH connection. |
| `dell_me_collection_duration_seconds` | gauge | - | Duration of the last full collection cycle. |
| `dell_me_last_success_unixtime` | gauge | - | Unix timestamp of the last fully successful collection cycle. |
| `dell_me_collection_errors_total` | counter | - | Number of collection cycles with at least one failed collector or SSH failure. |
| `dell_me_collector_up` | gauge | `collector` | `1` when the named collector succeeded in the last cycle. |
| `dell_me_collector_duration_seconds` | gauge | `collector` | Duration of the named collector in the last cycle. |
| `dell_me_collector_errors_total` | counter | `collector` | Number of failures for the named collector. |

### System and alerts

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `dell_me_system_health` | gauge | - | Overall system health. |
| `dell_me_system_info` | gauge | `name`, `model`, `serial_number`, `firmware` | Static system information. |
| `dell_me_active_alerts` | gauge | - | Number of unresolved alerts. |
| `dell_me_alerts` | gauge | `severity` | Number of unresolved alerts by severity: `critical`, `error`, `warning`, `informational`, `unknown`. |
| `dell_me_alert_info` | gauge | `slot`, `id`, `severity`, `component`, `description`, `reason`, `recommended_action`, `detected_time`, `resolved` | Text details for unresolved alerts, limited to 20 alert slots. |
| `dell_me_event_info` | gauge | `rank`, `id`, `severity`, `component`, `code`, `time`, `message` | Text details for the 20 most recent events from `show events`. |

### Controllers

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `dell_me_controller_health` | gauge | `controller` | Controller health is OK. |
| `dell_me_controller_operational` | gauge | `controller` | Controller status is Operational. |
| `dell_me_controller_failed_over` | gauge | `controller` | Controller is currently failed over. |
| `dell_me_controller_cache_lock` | gauge | `controller` | Controller cache lock is enabled. |
| `dell_me_controller_write_back` | gauge | `controller` | Controller write policy is write-back. |
| `dell_me_controller_memory_bytes` | gauge | `controller` | Controller system memory in bytes. |
| `dell_me_controller_cache_bytes` | gauge | `controller` | Controller cache memory in bytes. |
| `dell_me_controller_cpu_mhz` | gauge | `controller` | Controller CPU clock in MHz. |
| `dell_me_controller_redundant` | gauge | `controller` | Controller redundancy status is Redundant. |
| `dell_me_controller_info` | gauge | `controller`, `serial_number`, `model`, `firmware`, `hardware_version`, `ip_address`, `position` | Static controller information. |

### Ports

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `dell_me_management_link_up` | gauge | `controller` | Management interface link is up. |
| `dell_me_management_health` | gauge | `controller` | Management interface health is OK. |
| `dell_me_host_port_up` | gauge | `controller`, `port`, `media` | Host port link is up. |
| `dell_me_host_port_health` | gauge | `controller`, `port`, `media` | Host port health is OK. |
| `dell_me_host_port_speed_gbps` | gauge | `controller`, `port`, `media` | Host port negotiated speed in Gbit/s. |
| `dell_me_expander_port_up` | gauge | `controller`, `port` | Expansion port link is up. |
| `dell_me_expander_port_health` | gauge | `controller`, `port` | Expansion port health is OK. |
| `dell_me_expander_port_speed_gbps` | gauge | `controller`, `port` | Expansion port negotiated speed in Gbit/s. |

### Disks

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `dell_me_disk_health` | gauge | `disk`, `enclosure`, `slot` | Disk health is OK. |
| `dell_me_disk_online` | gauge | `disk`, `enclosure`, `slot` | Disk state is online/available. |
| `dell_me_disk_size_bytes` | gauge | `disk`, `enclosure`, `slot` | Disk raw size in bytes. |
| `dell_me_disk_temperature_celsius` | gauge | `disk`, `enclosure`, `slot` | Disk temperature in Celsius. |
| `dell_me_disk_rpm` | gauge | `disk`, `enclosure`, `slot` | Disk rotational speed; `0` for SSDs. |
| `dell_me_disk_life_remaining_percent` | gauge | `disk`, `enclosure`, `slot` | SSD life remaining percent. |
| `dell_me_disk_info` | gauge | `disk`, `enclosure`, `slot`, `serial_number`, `vendor`, `model`, `revision`, `type` | Static disk information. |

### Pools

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `dell_me_pool_health` | gauge | `pool` | Pool health is OK. |
| `dell_me_pool_size_bytes` | gauge | `pool` | Pool total capacity in bytes. |
| `dell_me_pool_used_bytes` | gauge | `pool` | Pool used capacity in bytes. |
| `dell_me_pool_free_bytes` | gauge | `pool` | Pool free capacity in bytes. |
| `dell_me_pool_used_percent` | gauge | `pool` | Pool used capacity percent. |

### Volumes

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `dell_me_volume_health` | gauge | `volume` | Volume health is OK. |
| `dell_me_volume_online` | gauge | `volume` | Volume is online/available. |
| `dell_me_volume_size_bytes` | gauge | `volume` | Volume size in bytes. |
| `dell_me_volume_allocated_bytes` | gauge | `volume` | Volume allocated capacity in bytes. |
| `dell_me_volume_used_percent` | gauge | `volume` | Volume allocated capacity percent. |
| `dell_me_volume_info` | gauge | `volume`, `serial_number`, `pool`, `raid_type`, `owner`, `type` | Static volume information. |

### Versions

| Metric | Type | Labels | Description |
| --- | --- | --- | --- |
| `dell_me_version_info` | gauge | `basetype`, `component`, `version`, `controller`, `bundle_status`, `bundle_base_version`, `build_date`, `sc_fw`, `sc_baselevel`, `sc_loader`, `sc_asic_version`, `mc_fw`, `mc_base_fw`, `mc_loader`, `mc_os_version`, `capi_version`, `ec_fw`, `cpld_version`, `hardware_version`, `him_version`, `him_model`, `help_version`, `translation_version` | Firmware/software version information from `show versions detail`; falls back to `show versions` if detail output is unavailable. |

## Prometheus scrape config

```yaml
scrape_configs:
  - job_name: dell-me5
    static_configs:
      - targets: ['monitoring-host:9824']
```

## Prometheus alert rules

Ready-to-use alert rules are available at:

```text
prometheus/dell-me5-alerts.yml
```

Example Prometheus configuration:

```yaml
rule_files:
  - /etc/prometheus/rules/dell-me5-alerts.yml
```

The rules cover:

- exporter scrape and SSH collection failures
- stale collection cycles
- failed collectors
- system, controller, disk, pool, volume, host port, and management health
- high pool and volume allocation
- unresolved critical and warning ME5 alerts

Review thresholds before production use, especially pool/volume usage and disk temperature.

## Grafana alert rules

Grafana-managed alert provisioning rules are available at:

```text
grafana/alerting/dell-me5-alerts.yml
```

The file uses `${GRAFANA_PROMETHEUS_DATASOURCE_UID}` as the Prometheus datasource UID. Set it to your Grafana Prometheus datasource UID before provisioning, for example:

```bash
export GRAFANA_PROMETHEUS_DATASOURCE_UID=prometheus
```

For Docker-based Grafana provisioning, mount the file into:

```text
/etc/grafana/provisioning/alerting/dell-me5-alerts.yml
```

## Grafana dashboard

A ready-to-import Grafana dashboard is available at:

```text
grafana/dell-me5-dashboard.json
```

Import it through **Dashboards → New → Import** and select your Prometheus datasource when prompted.

The dashboard includes:

- exporter and collector health
- unresolved alerts by severity and alert text details
- recent event text details
- pool capacity and utilization
- volume sizes
- controller status
- host and expansion port state
- disk health, inventory, and temperature
- firmware/software versions
