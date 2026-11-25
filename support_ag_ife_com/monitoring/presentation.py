from typing import Any


def server_indicator(server: dict[str, Any], limit: float) -> dict[str, str]:
    def status(kind: str, text: str) -> dict[str, str]:
        return {"kind": kind, "text": text}

    agent = server.get("agent")
    if not agent:
        return status("unknown", "Агент не настроен")
    if not agent.get("enabled"):
        return status("unknown", "Приём отключён")
    report = server.get("report")
    if not report:
        return status("unknown", "Нет отчётов")
    if report.get("error"):
        return status("bad", "Не удалось прочитать отчёт")
    checks = [check for check in report["checks"] if check["enabled"]]
    if not checks:
        return status("unknown", "Проверки отключены")
    unknown = False
    for check in checks:
        if check.get("error"):
            return status("bad", "Есть ошибки получения данных")
        results = [
            item for item in check["results"] if item.get("enabled") is not False
        ]
        if not results:
            unknown = True
        for item in results:
            if item.get("error"):
                return status("bad", "Есть ошибки получения данных")
            if check["type"] in {"network", "ping", "telnet"}:
                if item.get("reachable") is False:
                    return status("bad", "Есть недоступные подключения")
                if item.get("reachable") is not True:
                    unknown = True
            elif check["type"] == "memory":
                value = item.get("value")
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    unknown = True
                elif value >= limit:
                    return status("bad", "Превышен лимит заполнения диска")
            elif check["type"] == "content":
                details = item.get("details", {})
                count = details.get("err_total_count")
                if count is None:
                    count = details.get("err_count")
                if isinstance(count, (int, float)) and count > 0:
                    return status("bad", "В контенте обнаружены файлы .err")
    if unknown:
        return status("unknown", "Часть результатов отсутствует")
    return status("ok", "Проблем не обнаружено")
