"""Prometheus metric definitions for the ME5 exporter."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Info

# Exporter/self metrics
EXPORTER_UP = Gauge("dell_me_exporter_up", "1 when the last collection cycle completed with an SSH connection")
COLLECTION_DURATION = Gauge("dell_me_collection_duration_seconds", "Duration of the last collection cycle")
LAST_SUCCESS = Gauge("dell_me_last_success_unixtime", "Unix timestamp of the last fully successful collection cycle")
COLLECTION_ERRORS = Counter("dell_me_collection_errors", "Total failed collection cycles")
COLLECTOR_UP = Gauge("dell_me_collector_up", "1 when the collector command and parser succeeded", ["collector"])
COLLECTOR_DURATION = Gauge("dell_me_collector_duration_seconds", "Collector execution duration", ["collector"])
COLLECTOR_ERRORS = Counter("dell_me_collector_errors", "Collector failures", ["collector"])

# System
SYSTEM_HEALTH = Gauge("dell_me_system_health", "System health: 1=OK, 0=not OK or unknown")
SYSTEM_INFO = Info("dell_me_system", "Static ME system information")
ACTIVE_ALERTS = Gauge("dell_me_active_alerts", "Number of active alerts")
ALERTS_BY_SEVERITY = Gauge("dell_me_alerts", "Number of active alerts by severity", ["severity"])

# Controllers
CONTROLLER_HEALTH = Gauge("dell_me_controller_health", "Controller health: 1=OK", ["controller"])
CONTROLLER_OPERATIONAL = Gauge("dell_me_controller_operational", "Controller status is Operational", ["controller"])
CONTROLLER_FAILED_OVER = Gauge("dell_me_controller_failed_over", "Controller is currently failed over", ["controller"])
CONTROLLER_CACHE_LOCK = Gauge("dell_me_controller_cache_lock", "Controller cache lock enabled", ["controller"])
CONTROLLER_WRITE_BACK = Gauge("dell_me_controller_write_back", "Controller cache write policy is write-back", ["controller"])
CONTROLLER_MEMORY = Gauge("dell_me_controller_memory_bytes", "Controller system memory", ["controller"])
CONTROLLER_CACHE = Gauge("dell_me_controller_cache_bytes", "Controller cache memory", ["controller"])
CONTROLLER_CPU_MHZ = Gauge("dell_me_controller_cpu_mhz", "Controller CPU clock in MHz", ["controller"])
CONTROLLER_REDUNDANT = Gauge("dell_me_controller_redundant", "Controller redundancy status is Redundant", ["controller"])
CONTROLLER_INFO = Info("dell_me_controller", "Static controller information", ["controller"])

# Ports
MGMT_LINK_UP = Gauge("dell_me_management_link_up", "Management link is up", ["controller"])
MGMT_HEALTH = Gauge("dell_me_management_health", "Management interface health is OK", ["controller"])
HOST_PORT_UP = Gauge("dell_me_host_port_up", "Host port link status is Up", ["controller", "port", "media"])
HOST_PORT_HEALTH = Gauge("dell_me_host_port_health", "Host port health is OK", ["controller", "port", "media"])
HOST_PORT_SPEED_GBPS = Gauge("dell_me_host_port_speed_gbps", "Host port negotiated speed in Gbit/s", ["controller", "port", "media"])
EXPANDER_PORT_UP = Gauge("dell_me_expander_port_up", "Expansion port link status is Up", ["controller", "port"])
EXPANDER_PORT_HEALTH = Gauge("dell_me_expander_port_health", "Expansion port health is OK", ["controller", "port"])
EXPANDER_PORT_SPEED_GBPS = Gauge("dell_me_expander_port_speed_gbps", "Expansion port negotiated speed in Gbit/s", ["controller", "port"])

# Disks
DISK_HEALTH = Gauge("dell_me_disk_health", "Disk health is OK", ["disk", "enclosure", "slot"])
DISK_ONLINE = Gauge("dell_me_disk_online", "Disk state is online/available", ["disk", "enclosure", "slot"])
DISK_SIZE = Gauge("dell_me_disk_size_bytes", "Disk raw size", ["disk", "enclosure", "slot"])
DISK_TEMP = Gauge("dell_me_disk_temperature_celsius", "Disk temperature", ["disk", "enclosure", "slot"])
DISK_RPM = Gauge("dell_me_disk_rpm", "Disk rotational speed; zero for SSD", ["disk", "enclosure", "slot"])
DISK_LIFE = Gauge("dell_me_disk_life_remaining_percent", "SSD life remaining percent", ["disk", "enclosure", "slot"])
DISK_INFO = Info("dell_me_disk", "Static disk information", ["disk", "enclosure", "slot"])

# Pools
POOL_HEALTH = Gauge("dell_me_pool_health", "Pool health is OK", ["pool"])
POOL_SIZE = Gauge("dell_me_pool_size_bytes", "Pool total size", ["pool"])
POOL_USED = Gauge("dell_me_pool_used_bytes", "Pool used capacity", ["pool"])
POOL_FREE = Gauge("dell_me_pool_free_bytes", "Pool free capacity", ["pool"])
POOL_USED_PERCENT = Gauge("dell_me_pool_used_percent", "Pool used capacity percent", ["pool"])

# Volumes
VOLUME_HEALTH = Gauge("dell_me_volume_health", "Volume health is OK", ["volume"])
VOLUME_ONLINE = Gauge("dell_me_volume_online", "Volume is online/available", ["volume"])
VOLUME_SIZE = Gauge("dell_me_volume_size_bytes", "Volume size", ["volume"])
VOLUME_INFO = Info("dell_me_volume", "Static volume information", ["volume"])
