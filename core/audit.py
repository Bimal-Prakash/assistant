import logging
import datetime
import os
from core.config import BASE_DIR
from core.redactor import privacy_filter

logger = logging.getLogger("jarvis.core.audit")

class AuditLogger:
    def __init__(self, log_dir=None):
        self.log_dir = log_dir or os.path.join(BASE_DIR, "logs")
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        self.log_file = os.path.join(self.log_dir, "audit.log")

    def log_access(self, tool_name: str, data_access_tags: list, risk_tier: str):
        """
        Logs a metadata-only event indicating that sensitive data was accessed.
        """
        if not data_access_tags:
            return
            
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tags_str = ", ".join(data_access_tags)
        safe_tool_name = privacy_filter.scrub(tool_name)
        
        log_entry = f"[{timestamp}] [AUDIT] Tool '{safe_tool_name}' (Tier: {risk_tier}) accessed data category: [{tags_str}]\n"
        
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"Failed to write to audit log: {e}")

audit_logger = AuditLogger()
