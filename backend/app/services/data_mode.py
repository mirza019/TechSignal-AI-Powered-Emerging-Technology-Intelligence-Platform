from app.config import get_settings
from app.models import SystemSetting


def data_mode(db):
    """Workspace dataset selection; deployments can prohibit synthetic mode."""
    setting = db.get(SystemSetting, "data_mode")
    return bool(setting.value["is_demo"]) if setting else get_settings().demo_mode
