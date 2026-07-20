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
- `show ports`
- `show sas-link-health`
- `show versions detail`

Each collector can be disabled with `ENABLE_<NAME>=false`.

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
