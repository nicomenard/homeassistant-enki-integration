"""Constants for the Enki integration."""
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "enki"
NAME = "Enki"

DEFAULT_SCAN_INTERVAL = 30  # seconds

ENKI_OIDC_URL = "https://keycloak-prod.iot.leroymerlin.fr/realms/enki/protocol/openid-connect/token"
ENKI_BASE_URL = "https://enki.api.devportal.adeo.cloud"

# API gateway keys (captured from Enki app v2.23.0 via mitmproxy)
ENKI_HOME_API_KEY         = "FULsxyI3x1f7MtLVOsP6V1DeAPmBQJCB"
ENKI_BFF_API_KEY          = "hTFx7uzWpn2JRpeylsZRRK00hd7lxH3V"
ENKI_NODE_API_KEY         = "aMmVpSOOWjEGz7f99caaPdUPMNoAIabj"
ENKI_REFERENTIEL_API_KEY  = "MiodFO5my5FR5U1aWHfiGMgFSuL6eOmB"
ENKI_LIGHTS_API_KEY       = "3OVsNulRsUXfr7Hze54OHx8l6qDu2UcE"
ENKI_POWER_API_KEY        = "HaFUU0N7dDj1jIgMnrMAEdTWgKCH3Fhs"
ENKI_AIRFLOW_API_KEY      = "6ex5WlshxPnnNsqHGoyN5u6dCIIdbFYG"
ENKI_ESDK_API_KEY         = "oDEwPFCnkd6VVKxFsVCjQlDwPTeVskUA"

# ESDK ceiling fan: each physical endpoint maps to a controllable part
FAN_ENDPOINT  = 1   # fan motor
LIGHT_ENDPOINT = 2  # light kit

# Airflow modes reported by api-enki-airflow-prod
AIRFLOW_MODE_MANUAL = "MANUAL"
AIRFLOW_MODE_BREEZE = "BREEZE"

# Device type identifiers
DEVICE_TYPE_LIGHTS = "lights"       # referentiel type for standard light nodes
DEVICE_TYPE_FANS   = "ceiling_fans" # BFF metadata.deviceType for ESDK fan nodes

# Referentiel API version string (must match the app version)
REFERENTIEL_VERSION = "2.23.0"
