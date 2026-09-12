"""Session-only metrics; aggregated outputs contain no individual identifiers."""
from collections import deque


class SessionMetrics:
    def __init__(self):
        self.identities = set()
        self.observed_seconds = {}
        self.series = deque(maxlen=3600)
        self.last_t = None
        self.alerts = 0
        self.previous_alerts = 0

    def update(self, people, analytics, t):
        dt = max(0.,min(t-self.last_t,2.)) if self.last_t is not None else 0.
        self.last_t = t
        current = {p["id"] for p in people if not p.get("predicted")}
        self.identities.update(current)
        for pid in current:
            self.observed_seconds[pid] = self.observed_seconds.get(pid,0.)+dt
        alerts = sum(c["alert"] for c in analytics["clusters"])+sum(z.get("alert",False) for z in analytics["zones"])
        self.alerts += max(0,alerts-self.previous_alerts)
        self.previous_alerts = alerts
        if not self.series or t-self.series[-1]["t"] >= 1:
            self.series.append({"t":t,"count":len(current),"mapped":analytics["mappedCount"],"alerts":alerts})
        return {"observed":len(current),"identities":len(self.identities),"personSeconds":sum(self.observed_seconds.values()),"meanObservedSeconds":sum(self.observed_seconds.values())/max(1,len(self.identities)),"alerts":self.alerts}
