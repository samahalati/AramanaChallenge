from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    name = "monitoring"

    def ready(self):   # Observer wiring: monitoring subscribes to supervision's escalation signal
        from monitoring.services.escalation import on_issue_escalated
        from supervision.signals import issue_escalated
        issue_escalated.connect(on_issue_escalated, dispatch_uid="monitoring-escalation")
