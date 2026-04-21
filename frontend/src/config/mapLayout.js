export const REGION_COORDS = {
  rm: [51.0447, -114.0719],
  carstairs: [51.5668, -114.1017],
};

export const REGION_FALLBACK_COORDS = [50.0, -100.0];

export const REPLICA_COORDS = {
  rm: {
    "rm-1": [51.0607, -114.0919],
    "rm-2": [51.0287, -114.0519],
  },
  carstairs: {
    "carstairs-1": [51.5828, -114.1217],
    "carstairs-2": [51.5508, -114.0817],
  },
};

export const SITE_COORDS = {
  rm: {},
  carstairs: {
    "hospital-1": [51.5748, -114.0917],
    "hospital-2": [51.5588, -114.1117],
  },
};

export function getRegionCoords(regionName) {
  return REGION_COORDS[regionName] ?? REGION_FALLBACK_COORDS;
}

export function getReplicaCoords(regionName, replicaId, fallbackCenter) {
  const explicit = REPLICA_COORDS[regionName]?.[replicaId];
  if (explicit) return explicit;

  return fallbackCenter;
}

export function getSiteCoords(regionName, siteName) {
  return SITE_COORDS[regionName]?.[siteName] ?? null;
}