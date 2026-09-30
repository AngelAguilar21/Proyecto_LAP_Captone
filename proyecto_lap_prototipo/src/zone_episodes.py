"""Aggregate zone episodes in source time; missing evidence is not a zero count."""
import copy
import json
import uuid


def ensure_zone_ids(config):
    """Assign legacy IDs per plan, independent of list order; preserve saved IDs."""
    changed = False
    plans = [(config.get("planId", "custom"), config), *config.get("plans", {}).items()]
    for pid, plan in plans:
        seen = set()
        for zone in plan.get("zones", []):
            if zone.get("id") in (None, ""):
                seed = json.dumps([pid, zone.get("name"), zone.get("points")], sort_keys=True)
                zone["id"] = "zone-" + uuid.uuid5(uuid.NAMESPACE_URL, seed).hex
                changed = True
            zid = zone["id"]
            if not isinstance(zid, str) or not zid.strip() or len(zid) > 200 or zid in seen:
                raise ValueError("Las zonas de cada plano necesitan identificadores únicos.")
            seen.add(zid)
    return changed


def plan_observed(cameras, observed_ids, plan_id):
    """A plan needs a fresh, projectable sample from every participating camera.

    Partial coverage cannot establish a below-threshold count. Cached/adaptive
    density results are not evidence for this primary-tracking observation.
    """
    group = [c for c in cameras if c.get("planId", "custom") == plan_id]
    return bool(group) and all(c.get("projects") and c["id"] in observed_ids for c in group)


class ZoneEpisodes:
    def __init__(self, scope, namespace=None):
        self.scope = scope
        self.namespace = namespace
        self.active = {}
        self.history = {}
        self.clocks = {}

    def observe(self, zone, count, t, valid=True, context=None):
        zid = zone["id"]
        rule = zone.get("rule") or {}
        signature = json.dumps([zone["points"], rule, zone.get("kind"), context], sort_keys=True)
        episode = self.active.get(zid)
        if episode and not rule.get("enabled"):
            self.close(zid, max(episode["last"], t), "disabled")
            episode = None
        if episode and t < self.clocks[zid]:
            self.close(zid, episode["last"], "clock_reversed")
            episode = None
        if episode and episode["signature"] != signature:
            self.close(zid, episode["last"], "configuration_changed")
            episode = None
        self.clocks[zid] = t
        if not rule.get("enabled"):
            self.close(zid, t, "disabled")
            return None
        if not valid:
            if episode:
                episode["observed"] = False
            return episode
        if count < rule["minPeople"]:
            self.close(zid, t, "below_threshold")
            return None
        if episode is None:
            token = (uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(
                [self.namespace, self.scope, zid, t, signature, len(self.history)])).hex
                if self.namespace is not None else uuid.uuid4().hex)
            episode = dict(id=token, scope=self.scope, zoneId=zid,
                           zone=zone["name"], zoneName=zone["name"], start=t, last=t,
                           duration=0., peak=count, end=None, reason=None,
                           signature=signature, observed=True, alert=False,
                           threshold=rule["minPeople"], dwell=rule["dwell"])
            self.active[zid] = episode
            self.history[episode["id"]] = episode
        elif episode["observed"]:
            episode["duration"] += max(0., t - episode["last"])
        episode.update(last=t, observed=True, count=count, peak=max(episode["peak"], count),
                       zone=zone["name"], zoneName=zone["name"])
        episode["alert"] |= episode["duration"] >= rule["dwell"]
        return episode

    def close(self, zid, t, reason):
        episode = self.active.pop(zid, None)
        if episode:
            episode.update(end=max(episode["last"], t), reason=reason)

    def retain(self, zone_ids, t):
        for zid in set(self.active) - set(zone_ids):
            self.close(zid, t, "zone_removed")

    def finish(self, reason="session_ended"):
        for zid, episode in list(self.active.items()):
            self.close(zid, episode["last"], reason)

    def snapshot(self):
        return copy.deepcopy(list(self.history.values()))
