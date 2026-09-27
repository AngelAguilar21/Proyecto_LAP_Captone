"""Source-time episodes. Missing observations never prove an episode ended."""
import copy
import json
import uuid


def ensure_zone_ids(config):
    seen = set()
    for zone in config.get("zones", []):
        if not zone.get("id"):
            # Stable legacy assignment, independent of list order. Saved with config.
            seed = json.dumps([zone.get("name"), zone.get("points")], sort_keys=True)
            zone["id"] = "zone-" + uuid.uuid5(uuid.NAMESPACE_URL, seed).hex
        if not isinstance(zone["id"], str) or zone["id"] in seen:
            raise ValueError("Las zonas necesitan identificadores únicos.")
        seen.add(zone["id"])


class ZoneEpisodes:
    def __init__(self, scope):
        self.scope = scope
        self.active = {}
        self.history = {}

    def observe(self, zone, count, t, valid=True):
        zid = zone["id"]
        rule = zone.get("rule") or {}
        signature = json.dumps([zone["points"], rule], sort_keys=True)
        episode = self.active.get(zid)
        if episode and (episode["signature"] != signature or t < episode["last"]):
            self.close(zid, episode["last"], "configuration_or_clock_changed")
            episode = None
        if not valid:
            if episode:
                episode["observed"] = False
            return episode
        above = rule.get("enabled") and count >= rule["minPeople"]
        if not above:
            self.close(zid, t, "below_threshold" if rule.get("enabled") else "disabled")
            return None
        if episode is None:
            episode = dict(id=uuid.uuid4().hex, scope=self.scope, zone=zid, start=t,
                           last=t, duration=0., peak=count, end=None, reason=None,
                           signature=signature, observed=True, alert=False)
            self.active[zid] = episode
            self.history[episode["id"]] = episode
        elif episode["observed"]:
            episode["duration"] += max(0., t - episode["last"])
        episode.update(last=t, observed=True, peak=max(episode["peak"], count))
        episode["alert"] |= episode["duration"] >= rule["dwell"]
        return episode

    def close(self, zid, t, reason):
        episode = self.active.pop(zid, None)
        if episode:
            episode.update(end=t, reason=reason)

    def snapshot(self):
        return copy.deepcopy(list(self.history.values()))
