from src.connectors.platform.dynamics_connector import DynamicsConnector


class PowerPagesConnector(DynamicsConnector):
    connector_type = "power_pages_dataverse"
    source_system = "ms_power_pages"
    entity = "cr123_formsubmissions"


def register_connectors(registry, config=None):
    registry.register(PowerPagesConnector())
